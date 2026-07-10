from zoneinfo import ZoneInfo
from django.utils import timezone

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                profile.last_active_at = timezone.now()
                profile.save(update_fields=['last_active_at'])
            except Exception:
                pass
                
            try:
                tzname = request.user.profile.timezone
                if tzname:
                    timezone.activate(ZoneInfo(tzname))
            except Exception:
                timezone.deactivate()
        else:
            timezone.deactivate()
        return self.get_response(request)
