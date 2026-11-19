from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def gbp(value):
    """£60 instead of £60.00, but keep pence when there are any."""
    if value is None:
        return ""
    value = Decimal(value)
    if value == value.to_integral():
        return f"£{value:,.0f}"
    return f"£{value:,.2f}"


@register.filter
def minutes(value):
    value = int(value)
    if value < 60:
        return f"{value} min"
    hours, mins = divmod(value, 60)
    return f"{hours} hr {mins} min" if mins else f"{hours} hr"
