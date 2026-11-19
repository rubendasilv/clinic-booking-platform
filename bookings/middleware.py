UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign")


class CampaignTrackingMiddleware:
    """Remember which ad or post brought a visitor (?utm_source=tiktok...) so bookings record it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        found = {k: request.GET[k][:100] for k in UTM_KEYS if request.GET.get(k)}
        if found:
            request.session["campaign"] = found
        return self.get_response(request)
