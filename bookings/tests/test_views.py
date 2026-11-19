from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from bookings import actions, tasks
from bookings.models import Booking
from bookings.tokens import make_manage_token


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["home", "services", "products", "policies", "book", "health"])
def test_public_pages_load(client, service, open_every_day, name):
    assert client.get(reverse(f"bookings:{name}")).status_code == 200


@pytest.mark.django_db
def test_prices_page_shows_price(client, service):
    assert "£70" in client.get(reverse("bookings:services")).content.decode()


@pytest.mark.django_db
def test_slots_partial_lists_times(client, service, future_slot):
    response = client.get(
        reverse("bookings:slots"),
        {"service": service.pk, "date": future_slot.date().isoformat()},
    )
    assert response.status_code == 200
    assert "11:00" in response.content.decode()


def _form(service, start, **extra):
    data = {
        "service": service.pk,
        "start": start.isoformat(),
        "first_name": "Amara",
        "last_name": "Okafor",
        "email": "Amara@Example.com",
        "phone": "07700900123",
        "is_adult": "on",
        "accepts_policy": "on",
    }
    data.update(extra)
    return data


@pytest.mark.django_db
def test_booking_form_creates_booking_and_records_campaign(client, service, future_slot):
    client.get("/?utm_source=tiktok&utm_campaign=launch")
    response = client.post(reverse("bookings:book"), _form(service, future_slot))
    assert response.status_code == 302
    booking = Booking.objects.get()
    assert booking.customer.email == "amara@example.com"
    assert booking.utm_source == "tiktok"
    assert booking.utm_campaign == "launch"


@pytest.mark.django_db
def test_under_18_cannot_book(client, service, future_slot):
    data = _form(service, future_slot)
    del data["is_adult"]
    response = client.post(reverse("bookings:book"), data)
    assert response.status_code == 200
    assert "over-18s" in response.content.decode()
    assert not Booking.objects.exists()


@pytest.mark.django_db
def test_manage_link_cancels(client, service, customer, future_slot):
    booking = actions.create_booking(service=service, start=future_slot, customer=customer)
    url = reverse("bookings:manage", args=[make_manage_token(booking)])
    assert client.get(url).status_code == 200
    client.post(url, {"action": "cancel"})
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED


@pytest.mark.django_db
def test_tampered_manage_link_is_rejected(client, service, customer, future_slot):
    booking = actions.create_booking(service=service, start=future_slot, customer=customer)
    token = make_manage_token(booking)
    assert client.get(reverse("bookings:manage", args=[token[:-2] + "xx"])).status_code == 404


@pytest.mark.django_db
def test_dashboard_needs_staff_login(client, admin_client):
    assert client.get(reverse("bookings:dashboard")).status_code == 302
    assert admin_client.get(reverse("bookings:dashboard")).status_code == 200


@pytest.mark.django_db
def test_csv_export(admin_client, service, customer, future_slot):
    actions.create_booking(service=service, start=future_slot, customer=customer)
    response = admin_client.get(reverse("bookings:export_bookings"))
    lines = response.content.decode().strip().splitlines()
    assert lines[0].startswith("booking_id,created_at,start")
    assert len(lines) == 2


@pytest.mark.django_db
def test_due_reminders_are_sent_once(service, customer, open_every_day):
    start = timezone.now() + timedelta(hours=20)
    Booking.objects.create(
        service=service, customer=customer, start=start, status=Booking.Status.CONFIRMED
    )
    mail.outbox.clear()
    assert tasks.send_due_reminders() == 1
    assert tasks.send_due_reminders() == 0
    assert len([m for m in mail.outbox if "Reminder" in m.subject]) == 1


def test_email_task_retries_on_smtp_errors():
    import smtplib

    assert smtplib.SMTPException in tasks.send_booking_confirmation.autoretry_for
    assert tasks.send_booking_confirmation.retry_backoff is True


@pytest.mark.django_db
def test_reminder_subject_says_today_or_tomorrow(service, customer, open_every_day):
    from bookings.emails import build_client_email

    soon = timezone.localtime() + timedelta(hours=1)
    booking = Booking.objects.create(service=service, customer=customer, start=soon)
    word = "today" if soon.date() == timezone.localdate() else "tomorrow"
    assert word in build_client_email(booking, "reminder").subject
