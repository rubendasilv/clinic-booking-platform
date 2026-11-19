"""Load demo treatments, prices, products and opening hours.

Safe to run more than once: it only adds what is missing and never overwrites your edits.

python manage.py seed_demo                       # catalogue + opening hours
python manage.py seed_demo --admin               # also create a demo admin login
python manage.py seed_demo --demo-bookings 120   # also add fake past/future bookings
"""

import os
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking, Customer, OpeningHours, Product, Service
from bookings.slots import generate_slots, opening_for

C = Service.Category
SERVICES = [
    # slug, name, category, summary, minutes, price, from?, deposit, patch test?
    (
        "consultation",
        "Consultation and patch test",
        C.CONSULTATION,
        "Talk through your goals, check your skin and test-patch the area. Needed before a first "
        "treatment.",
        30,
        "0",
        False,
        "0",
        False,
    ),
    (
        "tattoo-xs",
        "Tattoo removal: extra small",
        C.TATTOO,
        "Up to 3 × 3 cm, such as a small symbol or initials.",
        15,
        "50",
        False,
        "20",
        True,
    ),
    (
        "tattoo-s",
        "Tattoo removal: small",
        C.TATTOO,
        "Up to 5 × 5 cm, such as a wrist or ankle tattoo.",
        20,
        "70",
        False,
        "20",
        True,
    ),
    (
        "tattoo-m",
        "Tattoo removal: medium",
        C.TATTOO,
        "Up to 10 × 10 cm, such as a forearm piece.",
        30,
        "110",
        False,
        "20",
        True,
    ),
    (
        "tattoo-l",
        "Tattoo removal: large",
        C.TATTOO,
        "Up to 15 × 15 cm. Larger pieces are priced at consultation.",
        45,
        "160",
        True,
        "30",
        True,
    ),
    (
        "brows",
        "Cosmetic tattoo fading (brows)",
        C.TATTOO,
        "Lightening microblading or powder brows before a redo or for full removal.",
        20,
        "80",
        False,
        "20",
        True,
    ),
    (
        "hair-lip",
        "Hair removal: upper lip",
        C.HAIR,
        "Per session. Most people need a course of 6 to 8.",
        15,
        "35",
        False,
        "20",
        True,
    ),
    (
        "hair-underarms",
        "Hair removal: underarms",
        C.HAIR,
        "Per session. Most people need a course of 6 to 8.",
        20,
        "45",
        False,
        "20",
        True,
    ),
    (
        "hair-bikini",
        "Hair removal: bikini line",
        C.HAIR,
        "Per session. Most people need a course of 6 to 8.",
        20,
        "55",
        False,
        "20",
        True,
    ),
    (
        "hair-lower-legs",
        "Hair removal: lower legs",
        C.HAIR,
        "Per session, knee to ankle.",
        45,
        "120",
        False,
        "30",
        True,
    ),
    (
        "hair-full-legs",
        "Hair removal: full legs",
        C.HAIR,
        "Per session, thigh to ankle.",
        60,
        "180",
        False,
        "30",
        True,
    ),
    (
        "hair-back",
        "Hair removal: back",
        C.HAIR,
        "Per session, full back and shoulders.",
        45,
        "140",
        False,
        "30",
        True,
    ),
]

PRODUCTS = [
    (
        "aftercare-balm",
        "Aftercare balm, 50 ml",
        "Fragrance-free balm for the days after a tattoo removal session.",
        "14",
        40,
    ),
    (
        "spf50",
        "Mineral SPF 50, 50 ml",
        "Treated skin must be protected from the sun between sessions.",
        "18",
        30,
    ),
    ("cooling-gel", "Cooling aloe gel, 100 ml", "Soothes skin after laser hair removal.", "10", 25),
    (
        "course-tattoo-s",
        "Course of 6: small tattoo removal",
        "Six sessions for the price of five. Book each session online as usual.",
        "350",
        99,
    ),
    (
        "voucher-50",
        "Gift voucher, £50",
        "Can be spent on any treatment or product. Valid for 12 months.",
        "50",
        999,
    ),
    (
        "voucher-100",
        "Gift voucher, £100",
        "Can be spent on any treatment or product. Valid for 12 months.",
        "100",
        999,
    ),
]

HOURS = {
    0: None,
    1: (time(10), time(19)),
    2: (time(10), time(19)),
    3: (time(10), time(19)),
    4: (time(10), time(19)),
    5: (time(9), time(17)),
    6: None,
}

FIRST = [
    "Amara",
    "Jay",
    "Priya",
    "Tom",
    "Leah",
    "Kwame",
    "Sofia",
    "Dan",
    "Chloe",
    "Ravi",
    "Ella",
    "Marcus",
    "Zara",
    "Sam",
    "Nadia",
    "Liam",
    "Aisha",
    "Joe",
    "Mia",
    "Tariq",
]
LAST = [
    "Okafor",
    "Patel",
    "Smith",
    "Nowak",
    "Silva",
    "Jones",
    "Khan",
    "Brown",
    "Evans",
    "Mensah",
    "Walsh",
    "Ahmed",
    "Taylor",
    "Costa",
    "Green",
]
SOURCES = [
    ("tiktok", "paid_social", 30),
    ("instagram", "paid_social", 25),
    ("facebook", "paid_social", 10),
    ("google", "organic", 15),
    ("", "", 20),
]


class Command(BaseCommand):
    help = "Load demo catalogue, opening hours and (optionally) an admin user and bookings."

    def add_arguments(self, parser):
        parser.add_argument("--admin", action="store_true", help="Create a demo admin user.")
        parser.add_argument("--demo-bookings", type=int, default=0, metavar="N")
        parser.add_argument("--seed", type=int, default=42, help="Random seed for fake data.")

    @transaction.atomic
    def handle(self, *args, **opts):
        for order, row in enumerate(SERVICES):
            slug, name, cat, summary, mins, price, is_from, deposit, patch = row
            Service.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "category": cat,
                    "summary": summary,
                    "duration_minutes": mins,
                    "price": Decimal(price),
                    "price_is_from": is_from,
                    "deposit": Decimal(deposit),
                    "requires_patch_test": patch,
                    "display_order": order,
                },
            )
        for order, (slug, name, desc, price, stock) in enumerate(PRODUCTS):
            Product.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "price": Decimal(price),
                    "stock": stock,
                    "display_order": order,
                },
            )
        for weekday, hours in HOURS.items():
            OpeningHours.objects.get_or_create(
                weekday=weekday,
                defaults={
                    "is_closed": hours is None,
                    "opens_at": hours[0] if hours else None,
                    "closes_at": hours[1] if hours else None,
                },
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue ready: {len(SERVICES)} treatments, {len(PRODUCTS)} products."
            )
        )

        if opts["admin"]:
            self._make_admin()
        if opts["demo_bookings"]:
            self._make_bookings(opts["demo_bookings"], random.Random(opts["seed"]))

    def _make_admin(self):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME") or "admin"
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not password:
            if not settings.DEBUG:
                self.stderr.write("Set DJANGO_SUPERUSER_PASSWORD to create an admin in production.")
                return
            password = "clearline-demo"
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Admin user '{username}' already exists.")
            return
        User.objects.create_superuser(username, f"{username}@example.com", password)
        self.stdout.write(self.style.SUCCESS(f"Admin login: {username} / {password}"))

    def _make_bookings(self, count, rng):
        if Booking.objects.filter(notes__startswith="[demo]").exists():
            self.stdout.write("Demo bookings already exist, skipping.")
            return
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        now = timezone.now()
        services = list(Service.objects.filter(is_active=True))
        weights = [
            5 if s.category == C.CONSULTATION else 3 if s.category == C.TATTOO else 2
            for s in services
        ]
        source_weights = [w for *_, w in SOURCES]
        made = 0
        attempts = 0
        while made < count and attempts < count * 20:
            attempts += 1
            day = today + timedelta(days=rng.randint(-60, 21))
            opens, closes = opening_for(day)
            if not opens:
                continue
            service = rng.choices(services, weights)[0]
            day_start = datetime.combine(day, time.min, tzinfo=tz)
            busy = list(
                Booking.objects.overlapping(day_start, day_start + timedelta(days=1)).values_list(
                    "start", "blocks_until"
                )
            )
            slots = generate_slots(
                day=day,
                opens_at=opens,
                closes_at=closes,
                duration=service.duration,
                buffer=timedelta(minutes=service.buffer_minutes),
                busy=busy,
                tz=tz,
            )
            if not slots:
                continue
            start = rng.choice(slots)
            if start > now and start < now + timedelta(hours=2):
                continue
            first, last = rng.choice(FIRST), rng.choice(LAST)
            customer, _ = Customer.objects.get_or_create(
                email=f"{first}.{last}{rng.randint(1, 60)}@example.com".lower(),
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "phone": f"07700 9{rng.randint(10000, 99999)}",
                },
            )
            src, medium, _ = rng.choices(SOURCES, source_weights)[0]
            if start < now:
                status = rng.choices(
                    [Booking.Status.COMPLETED, Booking.Status.NO_SHOW, Booking.Status.CANCELLED],
                    [85, 6, 9],
                )[0]
            else:
                status = rng.choices([Booking.Status.CONFIRMED, Booking.Status.CANCELLED], [92, 8])[
                    0
                ]
            booking = Booking.objects.create(
                customer=customer,
                service=service,
                start=start,
                status=status,
                price=service.price,
                deposit=service.deposit,
                deposit_paid=service.deposit > 0 and rng.random() < 0.7,
                source=Booking.Source.WEBSITE,
                utm_source=src,
                utm_medium=medium,
                utm_campaign="launch" if src else "",
                notes="[demo] generated booking",
            )
            lead = timedelta(
                days=rng.choice([0, 1, 2, 3, 5, 7, 10, 14, 21]), hours=rng.randint(1, 10)
            )
            Booking.objects.filter(pk=booking.pk).update(created_at=min(start - lead, now))
            made += 1
        self.stdout.write(self.style.SUCCESS(f"Added {made} demo bookings."))
