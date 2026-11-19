"""Optional Stripe deposits. With no STRIPE_SECRET_KEY set, deposits are taken in clinic."""

from django.conf import settings
from django.urls import reverse


def stripe_enabled():
    return bool(settings.STRIPE_SECRET_KEY)


def _stripe():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_deposit_checkout(booking, token):
    """Create a Stripe Checkout page for the deposit and return its URL."""
    stripe = _stripe()
    success = settings.SITE_URL + reverse("bookings:success", args=[token])
    cancel = settings.SITE_URL + reverse("bookings:manage", args=[token])
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=booking.customer.email,
        client_reference_id=str(booking.pk),
        metadata={"booking_id": str(booking.pk)},
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "gbp",
                    "unit_amount": int(booking.deposit * 100),
                    "product_data": {"name": f"Deposit: {booking.service.name}"},
                },
            }
        ],
        success_url=success + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel,
    )
    booking.stripe_session_id = session.id
    booking.save(update_fields=["stripe_session_id"])
    return session.url


def session_is_paid(session_id):
    session = _stripe().checkout.Session.retrieve(session_id)
    return session.payment_status == "paid", session


def parse_webhook(payload, signature):
    return _stripe().Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
