import threading
from datetime import timedelta

import pytest
from django.core import mail
from django.db import IntegrityError, connection, transaction

from bookings import actions
from bookings.models import Booking, Customer


@pytest.mark.django_db
def test_booking_is_confirmed_and_emails_are_sent(
    service, customer, future_slot, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        booking = actions.create_booking(service=service, start=future_slot, customer=customer)

    assert booking.status == Booking.Status.CONFIRMED
    assert booking.end == future_slot + timedelta(minutes=30)
    assert booking.blocks_until == future_slot + timedelta(minutes=40)
    subjects = [m.subject for m in mail.outbox]
    assert any("confirmed" in s for s in subjects)
    assert any("New booking" in s for s in subjects)


@pytest.mark.django_db
def test_confirmation_has_text_html_and_calendar_invite(
    service, customer, future_slot, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        actions.create_booking(service=service, start=future_slot, customer=customer)

    client_mail = next(m for m in mail.outbox if m.to == ["amara@example.com"])
    assert "Amara" in client_mail.body
    assert client_mail.alternatives[0][1] == "text/html"
    name, ics, mimetype = client_mail.attachments[0]
    assert name == "appointment.ics"
    assert "BEGIN:VEVENT" in ics and "DTSTART:" in ics


@pytest.mark.django_db
def test_same_slot_cannot_be_booked_twice(service, customer, future_slot):
    actions.create_booking(service=service, start=future_slot, customer=customer)
    other = Customer.objects.create(
        first_name="Jay", last_name="Patel", email="jay@example.com", phone="07700900456"
    )
    with pytest.raises(actions.SlotUnavailable):
        actions.create_booking(service=service, start=future_slot, customer=other)
    assert Booking.objects.count() == 1


@pytest.mark.django_db
def test_overlapping_slot_is_rejected(service, customer, future_slot):
    actions.create_booking(service=service, start=future_slot, customer=customer)
    with pytest.raises(actions.SlotUnavailable):
        actions.create_booking(
            service=service, start=future_slot + timedelta(minutes=15), customer=customer
        )


@pytest.mark.django_db
def test_database_blocks_overlap_even_without_the_app_check(service, customer, future_slot):
    Booking.objects.create(service=service, customer=customer, start=future_slot)
    with pytest.raises(IntegrityError), transaction.atomic():
        Booking.objects.create(
            service=service, customer=customer, start=future_slot + timedelta(minutes=20)
        )


@pytest.mark.django_db
def test_cancelled_booking_frees_the_slot(service, customer, future_slot):
    booking = actions.create_booking(service=service, start=future_slot, customer=customer)
    actions.cancel_booking(booking)
    again = actions.create_booking(service=service, start=future_slot, customer=customer)
    assert again.status == Booking.Status.CONFIRMED


@pytest.mark.django_db
def test_reschedule_moves_booking_and_emails(
    service, customer, future_slot, django_capture_on_commit_callbacks
):
    booking = actions.create_booking(service=service, start=future_slot, customer=customer)
    mail.outbox.clear()
    new_start = future_slot + timedelta(hours=2)
    with django_capture_on_commit_callbacks(execute=True):
        booking = actions.reschedule_booking(booking, new_start)
    assert booking.start == new_start
    assert booking.sequence == 1
    assert any("moved" in m.subject for m in mail.outbox)


@pytest.mark.django_db
def test_slot_outside_opening_hours_is_rejected(service, customer, future_slot):
    with pytest.raises(actions.SlotUnavailable):
        actions.create_booking(
            service=service, start=future_slot.replace(hour=20), customer=customer
        )


@pytest.mark.django_db
def test_unpaid_hold_expires_and_frees_slot(service, customer, future_slot, settings):
    booking = actions.create_booking(
        service=service, start=future_slot, customer=customer, take_deposit_online=True
    )
    assert booking.status == Booking.Status.PENDING_PAYMENT
    old = booking.created_at - timedelta(minutes=settings.BOOKING_RULES["unpaid_hold_minutes"] + 1)
    Booking.objects.filter(pk=booking.pk).update(created_at=old)

    other = actions.create_booking(service=service, start=future_slot, customer=customer)
    booking.refresh_from_db()
    assert booking.status == Booking.Status.EXPIRED
    assert other.status == Booking.Status.CONFIRMED


@pytest.mark.django_db(transaction=True)
def test_two_people_booking_at_once_only_one_wins(service, future_slot):
    """Simulate two clients pressing 'Confirm' at the same moment."""
    customers = [
        Customer.objects.create(
            first_name=f"C{i}", last_name="Test", email=f"c{i}@example.com", phone="0"
        )
        for i in range(2)
    ]
    results = []
    barrier = threading.Barrier(2)

    def attempt(c):
        try:
            barrier.wait()
            actions.create_booking(service=service, start=future_slot, customer=c)
            results.append("ok")
        except actions.SlotUnavailable:
            results.append("taken")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(c,)) for c in customers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["ok", "taken"]
    assert Booking.objects.active().count() == 1
