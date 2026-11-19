"""Numbers for the owner's dashboard and the CSV export used for forecasting (e.g. Monte Carlo)."""

import csv
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone

from .models import Booking, OpeningHours, Service
from .slots import opening_for

CSV_FIELDS = [
    "booking_id",
    "created_at",
    "start",
    "weekday",
    "hour",
    "lead_time_days",
    "service",
    "category",
    "duration_minutes",
    "price",
    "deposit",
    "deposit_paid",
    "status",
    "source",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "customer_id",
    "is_repeat_customer",
]


def booking_rows(queryset):
    first_booking = {}
    qs = queryset.select_related("service", "customer").order_by("created_at")
    for b in qs:
        start = timezone.localtime(b.start)
        created = timezone.localtime(b.created_at)
        is_repeat = b.customer_id in first_booking
        first_booking.setdefault(b.customer_id, b.pk)
        yield {
            "booking_id": b.pk,
            "created_at": created.isoformat(timespec="minutes"),
            "start": start.isoformat(timespec="minutes"),
            "weekday": start.strftime("%A"),
            "hour": start.hour,
            "lead_time_days": round((b.start - b.created_at).total_seconds() / 86400, 2),
            "service": b.service.name,
            "category": b.service.category,
            "duration_minutes": b.service.duration_minutes,
            "price": b.price,
            "deposit": b.deposit,
            "deposit_paid": int(b.deposit_paid),
            "status": b.status,
            "source": b.source,
            "utm_source": b.utm_source or "(direct)",
            "utm_medium": b.utm_medium,
            "utm_campaign": b.utm_campaign,
            "customer_id": b.customer_id,
            "is_repeat_customer": int(is_repeat),
        }


def bookings_csv_response(queryset, filename="bookings.csv"):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.DictWriter(response, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(booking_rows(queryset))
    return response


def services_csv_response():
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="services.csv"'
    writer = csv.writer(response)
    writer.writerow(
        ["service", "category", "price", "deposit", "duration_minutes", "buffer_minutes", "active"]
    )
    for s in Service.objects.all():
        writer.writerow(
            [
                s.name,
                s.category,
                s.price,
                s.deposit,
                s.duration_minutes,
                s.buffer_minutes,
                int(s.is_active),
            ]
        )
    # opening hours are needed to model capacity
    writer.writerow([])
    writer.writerow(["weekday", "is_closed", "opens_at", "closes_at"])
    for h in OpeningHours.objects.all():
        writer.writerow([h.get_weekday_display(), int(h.is_closed), h.opens_at, h.closes_at])
    return response


def _open_minutes(first_day, days):
    total = 0
    for i in range(days):
        day = first_day + timedelta(days=i)
        opens, closes = opening_for(day)
        if opens and closes:
            total += (datetime.combine(day, closes) - datetime.combine(day, opens)).seconds // 60
    return total


def dashboard_stats(now=None):
    now = now or timezone.now()
    tz = timezone.get_current_timezone()
    today = timezone.localtime(now).date()
    week_start = datetime.combine(today, time.min, tzinfo=tz)
    week_end = week_start + timedelta(days=7)
    month_ago = now - timedelta(days=30)

    upcoming = Booking.objects.filter(
        status=Booking.Status.CONFIRMED, start__gte=week_start, start__lt=week_end
    )
    booked_minutes = sum(b.service.duration_minutes for b in upcoming.select_related("service"))
    open_minutes = _open_minutes(today, 7)

    last_30 = Booking.objects.filter(start__gte=month_ago, start__lt=now)
    finished = last_30.filter(status__in=[Booking.Status.COMPLETED, Booking.Status.NO_SHOW])
    no_shows = finished.filter(status=Booking.Status.NO_SHOW).count()
    made_30 = Booking.objects.filter(created_at__gte=month_ago)
    cancelled_30 = made_30.filter(status=Booking.Status.CANCELLED).count()

    revenue = last_30.filter(status=Booking.Status.COMPLETED).aggregate(t=Sum("price"))["t"]

    by_service = (
        Booking.objects.filter(created_at__gte=month_ago)
        .exclude(status__in=[Booking.Status.EXPIRED])
        .values("service__name")
        .annotate(n=Count("id"), value=Sum("price", filter=~Q(status=Booking.Status.CANCELLED)))
        .order_by("-n")
    )
    by_source = (
        Booking.objects.filter(created_at__gte=month_ago)
        .exclude(status__in=[Booking.Status.EXPIRED])
        .values("utm_source")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    def with_share(rows, label_key):
        rows = list(rows)
        top = max((r["n"] for r in rows), default=0) or 1
        return [
            {
                "label": r[label_key] or "Direct / unknown",
                "n": r["n"],
                "value": r.get("value"),
                "pct": round(100 * r["n"] / top),
            }
            for r in rows
        ]

    return {
        "upcoming_count": upcoming.count(),
        "utilisation": round(100 * booked_minutes / open_minutes) if open_minutes else 0,
        "revenue_30": revenue or Decimal("0"),
        "bookings_made_30": made_30.count(),
        "no_show_rate": round(100 * no_shows / finished.count()) if finished.count() else None,
        "cancel_rate": round(100 * cancelled_30 / made_30.count()) if made_30.count() else None,
        "by_service": with_share(by_service, "service__name"),
        "by_source": with_share(by_source, "utm_source"),
        "next_bookings": Booking.objects.filter(status__in=Booking.ACTIVE_STATUSES, start__gte=now)
        .select_related("customer", "service")
        .order_by("start")[:10],
    }
