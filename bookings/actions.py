"""Everything that changes a booking goes through here, so the rules live in one place."""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import tasks
from .models import Booking, Customer
from .slots import available_slots


class SlotUnavailable(Exception):
    """The chosen time was taken (or is no longer bookable)."""


class BookingNotChangeable(Exception):
    """The booking is in the past, cancelled, or otherwise locked."""


def _send_after_commit(task, *args):
    # queue emails only once the database change is saved for good
    transaction.on_commit(lambda: task.delay(*args))


def _check_slot(service, start, exclude_booking=None):
    day = timezone.localtime(start).date()
    if start not in available_slots(service, day, exclude_booking=exclude_booking):
        raise SlotUnavailable("That time is no longer available. Please pick another.")


def upsert_customer(*, first_name, last_name, email, phone, marketing_opt_in=False):
    customer, created = Customer.objects.get_or_create(
        email=email.strip().lower(),
        defaults={
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "phone": phone.strip(),
            "marketing_opt_in": marketing_opt_in,
        },
    )
    if not created:
        # returning clients: keep their latest contact details
        customer.first_name = first_name.strip()
        customer.last_name = last_name.strip()
        customer.phone = phone.strip()
        customer.marketing_opt_in = customer.marketing_opt_in or marketing_opt_in
        customer.save()
    return customer


def create_booking(*, service, start, customer, notes="", campaign=None, take_deposit_online=False):
    """Book `service` at `start`. Raises SlotUnavailable if someone else got there first."""
    campaign = campaign or {}
    needs_payment = take_deposit_online and service.deposit > 0
    try:
        with transaction.atomic():
            # lock any live bookings around this time so two requests can't both pass the check
            list(
                Booking.objects.select_for_update().overlapping(
                    start - timedelta(hours=12), start + timedelta(hours=12)
                )
            )
            _check_slot(service, start)
            booking = Booking.objects.create(
                customer=customer,
                service=service,
                start=start,
                price=service.price,
                deposit=service.deposit,
                status=(
                    Booking.Status.PENDING_PAYMENT if needs_payment else Booking.Status.CONFIRMED
                ),
                notes=notes,
                source=Booking.Source.WEBSITE,
                utm_source=campaign.get("utm_source", "")[:100],
                utm_medium=campaign.get("utm_medium", "")[:100],
                utm_campaign=campaign.get("utm_campaign", "")[:100],
            )
    except IntegrityError as exc:
        # the database constraint is the last line of defence against double-booking
        raise SlotUnavailable("That time was just booked by someone else.") from exc

    if booking.status == Booking.Status.CONFIRMED:
        announce_new_booking(booking)
    return booking


def announce_new_booking(booking):
    _send_after_commit(tasks.send_booking_confirmation, booking.pk)
    _send_after_commit(tasks.notify_owner_new_booking, booking.pk)


def mark_deposit_paid(booking, stripe_session_id=""):
    """Called by the Stripe webhook / success page. Safe to call twice."""
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if booking.deposit_paid:
            return booking
        booking.deposit_paid = True
        if stripe_session_id:
            booking.stripe_session_id = stripe_session_id
        if booking.status in (Booking.Status.PENDING_PAYMENT, Booking.Status.EXPIRED):
            booking.status = Booking.Status.CONFIRMED
        try:
            # savepoint so a clash doesn't break the outer transaction
            with transaction.atomic():
                booking.save()
        except IntegrityError:
            # hold expired and someone else took the slot: flag it for the owner to refund
            booking.status = Booking.Status.CANCELLED
            booking.notes += "\n[System] Deposit paid after hold expired, slot taken. Refund."
            booking.save()
            _send_after_commit(tasks.notify_owner_problem, booking.pk)
            return booking
        announce_new_booking(booking)
    return booking


def _assert_changeable(booking):
    if not booking.is_upcoming:
        raise BookingNotChangeable("This booking can no longer be changed online.")


def is_late_change(booking, now=None):
    now = now or timezone.now()
    window = timedelta(hours=settings.BOOKING_RULES["cancellation_window_hours"])
    return booking.start - now < window


def cancel_booking(booking, *, by_client=True):
    _assert_changeable(booking)
    with transaction.atomic():
        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.sequence += 1
        booking.save()
        _send_after_commit(tasks.send_cancellation_notice, booking.pk)
        if by_client:
            _send_after_commit(tasks.notify_owner_change, booking.pk, "cancelled")
    return booking


def reschedule_booking(booking, new_start):
    _assert_changeable(booking)
    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking.pk)
            _check_slot(booking.service, new_start, exclude_booking=booking)
            booking.start = new_start
            booking.sequence += 1
            booking.reminder_sent_at = None
            booking.save()
    except IntegrityError as exc:
        raise SlotUnavailable("That time was just booked by someone else.") from exc
    _send_after_commit(tasks.send_reschedule_notice, booking.pk)
    _send_after_commit(tasks.notify_owner_change, booking.pk, "rescheduled")
    return booking
