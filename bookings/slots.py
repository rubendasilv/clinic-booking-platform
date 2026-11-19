"""Availability engine.

`generate_slots` is a pure function (no database) so it is easy to test.
`available_slots` gathers the data from the database and calls it.
"""

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone


def generate_slots(
    *,
    day: date,
    opens_at: time | None,
    closes_at: time | None,
    duration: timedelta,
    buffer: timedelta,
    busy: list[tuple[datetime, datetime]],
    tz,
    step: timedelta = timedelta(minutes=15),
    earliest: datetime | None = None,
) -> list[datetime]:
    """Return every start time on `day` where the service fits.

    A slot fits when:
    - the treatment itself finishes by closing time (the clean-down buffer may run past it),
    - the treatment plus buffer does not overlap any busy period,
    - it starts no earlier than `earliest` (minimum notice).
    """
    if opens_at is None or closes_at is None:
        return []

    opening = datetime.combine(day, opens_at, tzinfo=tz)
    closing = datetime.combine(day, closes_at, tzinfo=tz)
    slots = []
    start = opening
    while start + duration <= closing:
        blocked_until = start + duration + buffer
        clashes = any(start < b_end and blocked_until > b_start for b_start, b_end in busy)
        too_soon = earliest is not None and start < earliest
        if not clashes and not too_soon:
            slots.append(start)
        start += step
    return slots


def opening_for(day):
    """Return (opens_at, closes_at) for a date, or (None, None) when closed."""
    from .models import ClosedDay, OpeningHours

    if ClosedDay.objects.filter(date=day).exists():
        return None, None
    hours = OpeningHours.objects.filter(weekday=day.weekday()).first()
    if hours is None or hours.is_closed:
        return None, None
    return hours.opens_at, hours.closes_at


def bookable_window(now=None):
    """First and last dates a client may book."""
    rules = settings.BOOKING_RULES
    now = timezone.localtime(now or timezone.now())
    earliest = now + timedelta(hours=rules["min_notice_hours"])
    last_day = now.date() + timedelta(days=rules["max_days_ahead"])
    return earliest, last_day


def available_slots(service, day, *, now=None, exclude_booking=None):
    """Free start times for `service` on `day`, as timezone-aware datetimes."""
    from .models import Booking

    earliest, last_day = bookable_window(now)
    if day < earliest.date() or day > last_day:
        return []

    opens_at, closes_at = opening_for(day)
    tz = timezone.get_current_timezone()
    day_start = datetime.combine(day, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)

    # unpaid holds that timed out no longer block the diary
    Booking.objects.expired_holds(now).update(status=Booking.Status.EXPIRED)
    taken = Booking.objects.overlapping(day_start, day_end)
    if exclude_booking is not None:
        taken = taken.exclude(pk=exclude_booking.pk)
    busy = list(taken.values_list("start", "blocks_until"))

    return generate_slots(
        day=day,
        opens_at=opens_at,
        closes_at=closes_at,
        duration=service.duration,
        buffer=timedelta(minutes=service.buffer_minutes),
        busy=busy,
        tz=tz,
        step=timedelta(minutes=settings.BOOKING_RULES["slot_step_minutes"]),
        earliest=earliest,
    )


def upcoming_days(service, count=14, *, now=None):
    """The next `count` dates as (date, free slot count, is open) for the date picker."""
    earliest, last_day = bookable_window(now)
    days = []
    day = earliest.date()
    while len(days) < count and day <= last_day:
        is_open = opening_for(day)[0] is not None
        days.append((day, len(available_slots(service, day, now=now)), is_open))
        day += timedelta(days=1)
    return days
