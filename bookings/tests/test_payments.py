import pytest
from django.urls import reverse

from bookings import actions, payments
from bookings.models import Booking


@pytest.fixture
def held_booking(service, customer, future_slot):
    return actions.create_booking(
        service=service, start=future_slot, customer=customer, take_deposit_online=True
    )


@pytest.mark.django_db
def test_paid_webhook_confirms_booking(client, settings, monkeypatch, held_booking):
    settings.STRIPE_SECRET_KEY = "sk_test_dummy"
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "payment_status": "paid",
                "metadata": {"booking_id": str(held_booking.pk)},
            }
        },
    }
    monkeypatch.setattr(payments, "parse_webhook", lambda body, sig: event)
    response = client.post(
        reverse("bookings:stripe_webhook"), data=b"{}", content_type="application/json"
    )
    assert response.status_code == 200
    held_booking.refresh_from_db()
    assert held_booking.status == Booking.Status.CONFIRMED
    assert held_booking.deposit_paid


@pytest.mark.django_db
def test_paying_twice_is_harmless(held_booking):
    actions.mark_deposit_paid(held_booking, "cs_1")
    again = actions.mark_deposit_paid(held_booking, "cs_1")
    assert again.status == Booking.Status.CONFIRMED


@pytest.mark.django_db
def test_bad_signature_is_rejected(client, settings):
    settings.STRIPE_SECRET_KEY = "sk_test_dummy"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_dummy"
    response = client.post(
        reverse("bookings:stripe_webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=bad",
    )
    assert response.status_code == 400
