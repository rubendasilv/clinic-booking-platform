from django.conf import settings


def business(request):
    return {"business": settings.BUSINESS, "rules": settings.BOOKING_RULES}
