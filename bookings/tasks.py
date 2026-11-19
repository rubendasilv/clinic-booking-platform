"""Background jobs run by the Celery worker (and scheduled by Celery beat)."""

import logging
import smtplib
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# retry flaky email providers with growing waits: ~1s, 2s, 4s ... up to 10 minutes
RETRY = {
    "autoretry_for": (smtplib.SMTPException, ConnectionError, TimeoutError, OSError),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "retry_kwargs": {"max_retries": 6},
}


def _booking(pk):
    from .models import Booking

    return Booking.objects.select_related("customer", "service").get(pk=pk)


def _send_client(pk, kind):
    from .emails import build_client_email

    build_client_email(_booking(pk), kind).send()
    logger.info("Sent %s email for booking %s", kind, pk)


@shared_task(**RETRY)
def send_booking_confirmation(booking_id):
    _send_client(booking_id, "confirmation")


@shared_task(**RETRY)
def send_cancellation_notice(booking_id):
    _send_client(booking_id, "cancellation")


@shared_task(**RETRY)
def send_reschedule_notice(booking_id):
    _send_client(booking_id, "reschedule")


@shared_task(**RETRY)
def send_booking_reminder(booking_id):
    from .models import Booking

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        # skip if already sent, or cancelled since it was queued
        if booking.reminder_sent_at or booking.status != Booking.Status.CONFIRMED:
            return
        _send_client(booking_id, "reminder")
        booking.reminder_sent_at = timezone.now()
        booking.save(update_fields=["reminder_sent_at"])


@shared_task
def send_due_reminders():
    """Every 15 minutes: queue reminders for confirmed bookings starting in the next 24 hours."""
    from .models import Booking

    now = timezone.now()
    due = Booking.objects.filter(
        status=Booking.Status.CONFIRMED,
        reminder_sent_at__isnull=True,
        start__gt=now,
        start__lte=now + timedelta(hours=24),
    ).values_list("pk", flat=True)
    for pk in due:
        send_booking_reminder.delay(pk)
    return len(due)


@shared_task
def expire_unpaid_bookings():
    """Every 5 minutes: free up slots held for deposits that were never paid."""
    from .models import Booking

    return Booking.objects.expired_holds().update(status=Booking.Status.EXPIRED)


def _send_owner(pk, event):
    from .emails import build_owner_email

    build_owner_email(_booking(pk), event).send()


@shared_task(**RETRY)
def notify_owner_new_booking(booking_id):
    _send_owner(booking_id, "New booking")


@shared_task(**RETRY)
def notify_owner_change(booking_id, change):
    _send_owner(booking_id, f"Booking {change}")


@shared_task(**RETRY)
def notify_owner_problem(booking_id):
    _send_owner(booking_id, "Action needed: refund deposit")
