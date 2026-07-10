import re
from django.utils import timezone
import datetime
from .models import Reminder

def user_first_name_processor(request):
    context = {'user_first_name': '', 'today_active_count': 0}
    if request.user and request.user.is_authenticated:
        user = request.user
        if user.first_name:
            first_name = user.first_name.strip().split()[0].capitalize()
        else:
            # Extract first word/part of username before any symbols or digits as first name
            name_part = re.split(r'[-_\s\d]+', user.username)[0]
            if name_part:
                first_name = name_part.capitalize()
            else:
                first_name = user.username.capitalize()
        context['user_first_name'] = first_name
        
        if not user.is_superuser:
            try:
                now = timezone.now()
                start_of_day = timezone.make_aware(datetime.datetime.combine(now.date(), datetime.time.min))
                end_of_day = timezone.make_aware(datetime.datetime.combine(now.date(), datetime.time.max))
                
                count = Reminder.objects.filter(
                    user=user,
                    status__in=['pending', 'upcoming', 'confirmed'],
                    scheduled_time__range=(start_of_day, end_of_day)
                ).count()
                context['today_active_count'] = count
            except Exception as e:
                print(f"Error calculating today active reminders count in context processor: {e}")
                
    return context
