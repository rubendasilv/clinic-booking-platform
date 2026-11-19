from datetime import timedelta
from decimal import Decimal

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Func, Q
from django.urls import reverse
from django.utils import timezone


class TsTzRange(Func):
    """SQL tstzrange(start, end) so Postgres can compare time ranges."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Service(models.Model):
    class Category(models.TextChoices):
        CONSULTATION = "consultation", "Consultations"
        TATTOO = "tattoo", "Laser tattoo removal"
        HAIR = "hair", "Laser hair removal"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    summary = models.CharField(max_length=200, help_text="One line shown on the price list.")
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(validators=[MinValueValidator(5)])
    buffer_minutes = models.PositiveIntegerField(
        default=10, help_text="Clean-down time kept free after each appointment."
    )
    price = models.DecimalField(max_digits=8, decimal_places=2)
    price_is_from = models.BooleanField(
        default=False, help_text="Show the price as 'from £x' (final price set at consultation)."
    )
    deposit = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Taken online when Stripe is set up; otherwise paid in clinic.",
    )
    requires_patch_test = models.BooleanField(
        default=True, help_text="Remind clients they need a patch test before a first treatment."
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "display_order", "name"]

    def __str__(self):
        return self.name

    @property
    def duration(self):
        return timedelta(minutes=self.duration_minutes)

    @property
    def blocked_time(self):
        return timedelta(minutes=self.duration_minutes + self.buffer_minutes)


class Product(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0


class OpeningHours(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices, unique=True)
    is_closed = models.BooleanField(default=False)
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["weekday"]
        verbose_name_plural = "opening hours"

    def __str__(self):
        if self.is_closed:
            return f"{self.get_weekday_display()}: closed"
        return f"{self.get_weekday_display()}: {self.opens_at:%H:%M}–{self.closes_at:%H:%M}"

    def clean(self):
        if not self.is_closed:
            if not (self.opens_at and self.closes_at):
                raise ValidationError("Set opening and closing times, or tick 'is closed'.")
            if self.opens_at >= self.closes_at:
                raise ValidationError("Closing time must be after opening time.")


class ClosedDay(models.Model):
    """One-off closures: bank holidays, training days, holidays."""

    date = models.DateField(unique=True)
    reason = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%a %d %b %Y} {self.reason}".strip()


class Customer(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30)
    marketing_opt_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class BookingQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=Booking.ACTIVE_STATUSES)

    def overlapping(self, start, end):
        return self.active().filter(start__lt=end, blocks_until__gt=start)

    def expired_holds(self, now=None):
        from django.conf import settings

        now = now or timezone.now()
        cutoff = now - timedelta(minutes=settings.BOOKING_RULES["unpaid_hold_minutes"])
        return self.filter(status=Booking.Status.PENDING_PAYMENT, created_at__lt=cutoff)


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Awaiting deposit"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No-show"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired (deposit not paid)"

    ACTIVE_STATUSES = [Status.PENDING_PAYMENT, Status.CONFIRMED]

    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        ADMIN = "admin", "Added by staff"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    start = models.DateTimeField()
    end = models.DateTimeField(editable=False)
    blocks_until = models.DateTimeField(
        editable=False, help_text="End time plus clean-down buffer."
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    price = models.DecimalField(max_digits=8, decimal_places=2, editable=False)
    deposit = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    deposit_paid = models.BooleanField(default=False)
    stripe_session_id = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True, help_text="Anything the client wants us to know.")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ADMIN)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    sequence = models.PositiveIntegerField(default=0, editable=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BookingQuerySet.as_manager()

    class Meta:
        ordering = ["-start"]
        constraints = [
            # two live bookings can never start at the same moment
            models.UniqueConstraint(
                fields=["start"],
                condition=Q(status__in=["pending_payment", "confirmed"]),
                name="unique_active_booking_start",
            ),
            # and live bookings (plus their buffer) can never overlap at all
            ExclusionConstraint(
                name="no_overlapping_active_bookings",
                expressions=[
                    (TsTzRange("start", "blocks_until", RangeBoundary()), RangeOperators.OVERLAPS)
                ],
                condition=Q(status__in=["pending_payment", "confirmed"]),
            ),
            models.CheckConstraint(
                condition=Q(end__gt=models.F("start")), name="booking_end_after_start"
            ),
        ]
        indexes = [models.Index(fields=["status", "start"])]

    def __str__(self):
        when = timezone.localtime(self.start).strftime("%a %d %b %Y %H:%M")
        return f"{self.service} for {self.customer.full_name} on {when}"

    def save(self, *args, **kwargs):
        self.set_times()
        if self.price is None:
            self.price = self.service.price
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_upcoming(self):
        return self.is_active and self.start > timezone.now()

    def set_times(self):
        self.end = self.start + self.service.duration
        self.blocks_until = self.start + self.service.blocked_time

    def clean(self):
        # admin form check so staff get a friendly error instead of a database error
        if not (self.start and self.service_id):
            return
        self.set_times()
        if self.status in self.ACTIVE_STATUSES:
            clash = Booking.objects.overlapping(self.start, self.blocks_until).exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError({"start": f"This overlaps another booking: {clash.first()}"})

    def get_manage_url(self):
        from .tokens import make_manage_token

        return reverse("bookings:manage", args=[make_manage_token(self)])
