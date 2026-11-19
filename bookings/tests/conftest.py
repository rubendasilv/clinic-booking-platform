from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from bookings.models import Customer, OpeningHours, Service


@pytest.fixture(autouse=True)
def _test_settings(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.STRIPE_SECRET_KEY = ""
    settings.SITE_URL = "http://testserver"


@pytest.fixture
def open_every_day(db):
    for weekday in range(7):
        OpeningHours.objects.create(weekday=weekday, opens_at=time(10), closes_at=time(18))


@pytest.fixture
def service(db):
    return Service.objects.create(
        name="Tattoo removal: small",
        slug="tattoo-s",
        category=Service.Category.TATTOO,
        summary="Up to 5 x 5 cm",
        duration_minutes=30,
        buffer_minutes=10,
        price=Decimal("70"),
        deposit=Decimal("20"),
    )


@pytest.fixture
def customer(db):
    return Customer.objects.create(
        first_name="Amara", last_name="Okafor", email="amara@example.com", phone="07700900123"
    )


@pytest.fixture
def future_slot(open_every_day):
    """11:00 three days from now, local time."""
    day = timezone.localdate() + timedelta(days=3)
    return timezone.make_aware(datetime.combine(day, time(11)))
