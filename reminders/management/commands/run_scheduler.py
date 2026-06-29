import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from reminders.models import Reminder, ActivityLog

class Command(BaseCommand):
    help = 'Runs the background scheduler to dispatch due reminders'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Recallify background scheduler started...'))
        
        while True:
            try:
                now = timezone.now()
                due_reminders = Reminder.objects.filter(
                    scheduled_time__lte=now,
                    status__in=['pending', 'upcoming', 'confirmed']
                )
                
                if due_reminders.exists():
                    self.stdout.write(self.style.WARNING(f"Found {due_reminders.count()} due reminders at {now}"))
                    
                    for reminder in due_reminders:
                        # 1. Trigger Notification Simulation
                        self.stdout.write(self.style.SUCCESS(
                            f"[NOTIFICATION SENT] User: {reminder.user.username} | Title: {reminder.title} | Time: {reminder.scheduled_time}"
                        ))
                        
                        # 2. Update status to 'sent'
                        reminder.status = 'sent'
                        reminder.save()
                        
                        # 3. Create ActivityLog entry
                        ActivityLog.objects.create(
                            user=reminder.user,
                            action_type='Reminder Notification Sent',
                            details=f"Notification dispatched for reminder: '{reminder.title}' scheduled for {reminder.scheduled_time}."
                        )
                
                # Check for due reminders every 10 seconds
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS('Scheduler stopped by user.'))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in scheduler: {str(e)}"))
                time.sleep(10)
