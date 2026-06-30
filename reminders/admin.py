from django.contrib import admin
from .models import UserProfile, Reminder, ActivityLog

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription_tier', 'reminder_limit', 'created_at')
    list_filter = ('subscription_tier',)
    search_fields = ('user__username', 'user__email')

@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'scheduled_time', 'source', 'status', 'created_at')
    list_filter = ('status', 'source', 'scheduled_time')
    search_fields = ('title', 'description', 'user__username')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'details', 'timestamp')
    list_filter = ('action_type', 'timestamp')
    search_fields = ('user__username', 'action_type', 'details')

