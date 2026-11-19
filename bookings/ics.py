"""Build .ics calendar files (RFC 5545) so clients can add appointments to their calendar."""

from datetime import UTC
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone


def _escape(text):
    return (
        str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


def _fmt(dt):
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _fold(line):
    # RFC 5545: lines longer than 75 octets continue on the next line after a space
    out = []
    while len(line.encode()) > 75:
        cut = 75
        while len(line[:cut].encode()) > 75:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return "\r\n".join(out)


def booking_ics(booking, *, cancelled=False):
    business = settings.BUSINESS
    domain = urlparse(settings.SITE_URL).hostname or "localhost"
    manage_url = settings.SITE_URL + booking.get_manage_url()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{_escape(business['name'])}//Bookings//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{'CANCEL' if cancelled else 'PUBLISH'}",
        "BEGIN:VEVENT",
        f"UID:booking-{booking.pk}@{domain}",
        f"SEQUENCE:{booking.sequence}",
        f"DTSTAMP:{_fmt(timezone.now())}",
        f"DTSTART:{_fmt(booking.start)}",
        f"DTEND:{_fmt(booking.end)}",
        f"SUMMARY:{_escape(booking.service.name + ' at ' + business['name'])}",
        f"LOCATION:{_escape(business['address'])}",
        f"DESCRIPTION:{_escape('Manage your booking: ' + manage_url)}",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
    ]
    if not cancelled:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:Appointment reminder",
            "TRIGGER:-PT2H",
            "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
