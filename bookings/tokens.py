"""Signed, tamper-proof links so clients can manage a booking without an account."""

from django.conf import settings
from django.core import signing

SALT = "bookings.manage"


def make_manage_token(booking):
    # signing.dumps uses a TimestampSigner under the hood, so links can expire
    return signing.dumps({"b": booking.pk, "c": booking.customer_id}, salt=SALT, compress=True)


def read_manage_token(token):
    """Return (booking_pk, customer_pk) or raise signing.BadSignature."""
    max_age = settings.BOOKING_RULES["manage_link_max_age_days"] * 24 * 3600
    data = signing.loads(token, salt=SALT, max_age=max_age)
    return data["b"], data["c"]
