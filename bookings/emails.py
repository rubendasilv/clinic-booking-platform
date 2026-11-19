"""Build the emails. Sending happens in tasks.py so it runs in the background."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .booking_context import booking_context
from .ics import booking_ics

TEMPLATES = {
    "confirmation": "Your booking is confirmed: {service}, {when}",
    "reminder": "Reminder: {service} {day_word} at {time}",
    "cancellation": "Your booking has been cancelled",
    "reschedule": "Your booking has moved to {when}",
}


def build_client_email(booking, kind):
    ctx = booking_context(booking)
    subject = TEMPLATES[kind].format(**ctx["subject_bits"])
    text = render_to_string(f"emails/{kind}.txt", ctx)
    html = render_to_string(f"emails/{kind}.html", ctx)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[booking.customer.email],
        reply_to=[settings.BUSINESS["email"]],
    )
    msg.attach_alternative(html, "text/html")
    if kind != "reminder":
        msg.attach(
            "appointment.ics",
            booking_ics(booking, cancelled=(kind == "cancellation")),
            "text/calendar; charset=utf-8",
        )
    return msg


def build_owner_email(booking, event):
    ctx = booking_context(booking)
    ctx["event"] = event
    subject = f"[{event}] {ctx['subject_bits']['service']}, {ctx['subject_bits']['when']}"
    text = render_to_string("emails/owner_alert.txt", ctx)
    return EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.OWNER_NOTIFICATION_EMAIL],
    )
