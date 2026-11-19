"""Shared template context for emails and pages about one booking."""

from django.conf import settings
from django.utils import timezone


def booking_context(booking):
    start = timezone.localtime(booking.start)
    end = timezone.localtime(booking.end)
    days_away = (start.date() - timezone.localdate()).days
    day_word = {0: "today", 1: "tomorrow"}.get(days_away, start.strftime("on %A"))
    manage_url = settings.SITE_URL + booking.get_manage_url()
    return {
        "booking": booking,
        "customer": booking.customer,
        "service": booking.service,
        "start": start,
        "end": end,
        "manage_url": manage_url,
        "site_url": settings.SITE_URL,
        "business": settings.BUSINESS,
        "rules": settings.BOOKING_RULES,
        "day_word": day_word,
        "subject_bits": {
            "service": booking.service.name,
            "when": start.strftime("%a %-d %b at %H:%M"),
            "time": start.strftime("%H:%M"),
            "day_word": day_word,
        },
    }
