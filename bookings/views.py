import logging
from datetime import date

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core import signing
from django.db import connection
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import actions, analytics, payments
from .forms import BookingForm, RescheduleForm
from .models import Booking, OpeningHours, Product, Service
from .slots import available_slots, upcoming_days
from .tokens import make_manage_token, read_manage_token

logger = logging.getLogger(__name__)


def _grouped_services():
    services = Service.objects.filter(is_active=True)
    groups = []
    for value, label in Service.Category.choices:
        items = [s for s in services if s.category == value]
        if items:
            groups.append({"key": value, "label": label, "services": items})
    return groups


# --- Public pages ---


def home(request):
    return render(
        request,
        "bookings/home.html",
        {
            "groups": _grouped_services(),
            "consultation": Service.objects.filter(
                is_active=True, category=Service.Category.CONSULTATION
            ).first(),
            "hours": OpeningHours.objects.all(),
        },
    )


def services(request):
    return render(request, "bookings/services.html", {"groups": _grouped_services()})


def products(request):
    return render(
        request, "bookings/products.html", {"products": Product.objects.filter(is_active=True)}
    )


def policies(request):
    return render(request, "bookings/policies.html", {"hours": OpeningHours.objects.all()})


# --- Booking flow ---


def _parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@require_http_methods(["GET", "POST"])
def book(request):
    service = None
    slug = request.GET.get("service") or request.POST.get("service_slug")
    if slug:
        service = Service.objects.filter(slug=slug, is_active=True).first()

    form = BookingForm(request.POST or None, initial={"service": service})
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        service = data["service"]
        customer = actions.upsert_customer(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone=data["phone"],
            marketing_opt_in=data["marketing_opt_in"],
        )
        try:
            booking = actions.create_booking(
                service=service,
                start=data["start"],
                customer=customer,
                notes=data["notes"],
                campaign=request.session.get("campaign"),
                take_deposit_online=payments.stripe_enabled(),
            )
        except actions.SlotUnavailable as exc:
            form.add_error("start", str(exc))
        else:
            token = make_manage_token(booking)
            if booking.status == Booking.Status.PENDING_PAYMENT:
                try:
                    return redirect(payments.create_deposit_checkout(booking, token))
                except Exception:
                    logger.exception("Stripe checkout failed for booking %s", booking.pk)
                    booking.status = Booking.Status.CONFIRMED
                    booking.save(update_fields=["status"])
                    actions.announce_new_booking(booking)
            return redirect("bookings:success", token=token)
    elif request.method == "POST" and form.cleaned_data.get("service"):
        service = form.cleaned_data["service"]

    context = {
        "form": form,
        "groups": _grouped_services(),
        "service": service,
        "selected_start": request.POST.get("start", ""),
    }
    if service:
        context["days"] = upcoming_days(service)
    return render(request, "bookings/book.html", context)


@require_GET
def days_partial(request):
    """HTMX: date strip for the chosen service."""
    service = get_object_or_404(Service, pk=request.GET.get("service"), is_active=True)
    return render(
        request,
        "bookings/partials/days.html",
        {"service": service, "days": upcoming_days(service)},
    )


@require_GET
def slots_partial(request):
    """HTMX: free times for one service on one day."""
    service = get_object_or_404(Service, pk=request.GET.get("service"), is_active=True)
    day = _parse_day(request.GET.get("date"))
    if day is None:
        return HttpResponseBadRequest("Pick a valid date.")
    exclude = None
    if request.GET.get("token"):
        exclude = _booking_from_token(request.GET["token"])
    slots = available_slots(service, day, exclude_booking=exclude)
    return render(
        request,
        "bookings/partials/slots.html",
        {"service": service, "day": day, "slots": slots, "selected": request.GET.get("selected")},
    )


def _booking_from_token(token):
    try:
        booking_pk, customer_pk = read_manage_token(token)
    except signing.BadSignature as exc:
        raise Http404("This link is invalid or has expired.") from exc
    return get_object_or_404(
        Booking.objects.select_related("service", "customer"), pk=booking_pk, customer=customer_pk
    )


def success(request, token):
    booking = _booking_from_token(token)
    session_id = request.GET.get("session_id")
    if session_id and not booking.deposit_paid and payments.stripe_enabled():
        # confirm straight away instead of waiting for the webhook
        try:
            paid, _ = payments.session_is_paid(session_id)
            if paid and session_id == booking.stripe_session_id:
                booking = actions.mark_deposit_paid(booking, session_id)
        except Exception:
            logger.exception("Could not verify Stripe session %s", session_id)
    return render(
        request,
        "bookings/success.html",
        {"booking": booking, "token": token, "start": timezone.localtime(booking.start)},
    )


@require_http_methods(["GET", "POST"])
def manage(request, token):
    booking = _booking_from_token(token)
    late = actions.is_late_change(booking)

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "cancel":
                actions.cancel_booking(booking)
                messages.success(request, "Your booking has been cancelled. We've emailed you.")
            elif action == "reschedule":
                form = RescheduleForm(request.POST)
                if form.is_valid():
                    actions.reschedule_booking(booking, form.cleaned_data["start"])
                    messages.success(request, "Your booking has been moved. We've emailed you.")
                else:
                    messages.error(request, "Choose a new time from the list.")
            elif action == "pay" and booking.status == Booking.Status.PENDING_PAYMENT:
                return redirect(payments.create_deposit_checkout(booking, token))
        except (actions.SlotUnavailable, actions.BookingNotChangeable) as exc:
            messages.error(request, str(exc))
        return redirect("bookings:manage", token=token)

    return render(
        request,
        "bookings/manage.html",
        {
            "booking": booking,
            "token": token,
            "late": late,
            "start": timezone.localtime(booking.start),
            "days": upcoming_days(booking.service) if booking.is_upcoming else [],
        },
    )


# --- Payments ---


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not payments.stripe_enabled():
        raise Http404
    try:
        event = payments.parse_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except Exception:
        return HttpResponseBadRequest("Invalid signature")
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        booking_id = (session.get("metadata") or {}).get("booking_id")
        booking = Booking.objects.filter(pk=booking_id).first()
        if booking and session.get("payment_status") == "paid":
            actions.mark_deposit_paid(booking, session["id"])
    return HttpResponse(status=200)


# --- Owner tools ---


@staff_member_required
def dashboard(request):
    return render(request, "bookings/dashboard.html", analytics.dashboard_stats())


@staff_member_required
def export_bookings(request):
    stamp = timezone.localdate().isoformat()
    return analytics.bookings_csv_response(Booking.objects.all(), f"bookings-{stamp}.csv")


@staff_member_required
def export_services(request):
    return analytics.services_csv_response()


# --- Ops ---


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "database": "ok"})
    except Exception:
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)
