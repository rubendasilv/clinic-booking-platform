from datetime import datetime

from django import forms
from django.utils import timezone

from .models import Service


class SlotField(forms.CharField):
    """A start time posted as an ISO string, turned back into an aware datetime."""

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as exc:
            raise forms.ValidationError("Choose a time from the list.") from exc
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt


class BookingForm(forms.Form):
    service = forms.ModelChoiceField(queryset=Service.objects.filter(is_active=True))
    start = SlotField(error_messages={"required": "Choose a time for your appointment."})
    first_name = forms.CharField(max_length=80, label="First name")
    last_name = forms.CharField(max_length=80, label="Last name")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(max_length=30, label="Mobile number")
    notes = forms.CharField(
        required=False,
        label="Anything we should know? (optional)",
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=1000,
    )
    is_adult = forms.BooleanField(
        label="I am 18 or over",
        error_messages={"required": "Laser treatments are only available to over-18s."},
    )
    accepts_policy = forms.BooleanField(
        label="I have read the booking and cancellation policy",
        error_messages={"required": "Please confirm you have read the policy."},
    )
    marketing_opt_in = forms.BooleanField(
        required=False, label="Send me occasional offers by email"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        autocomplete = {
            "first_name": "given-name",
            "last_name": "family-name",
            "email": "email",
            "phone": "tel",
        }
        for name, value in autocomplete.items():
            self.fields[name].widget.attrs["autocomplete"] = value
        self.fields["phone"].widget.input_type = "tel"


class RescheduleForm(forms.Form):
    start = SlotField(error_messages={"required": "Choose a new time."})
