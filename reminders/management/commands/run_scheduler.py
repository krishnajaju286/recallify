import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from reminders.models import Reminder, ActivityLog

class Command(BaseCommand):
    help = 'Runs the background scheduler to dispatch due reminders'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Recallify background scheduler started...'))
        
        while True:
            try:
                now = timezone.now()
                # Fetch pending/upcoming/confirmed reminders that are due
                due_reminders = Reminder.objects.filter(
                    scheduled_time__lte=now,
                    status__in=['pending', 'upcoming', 'confirmed']
                )
                
                if due_reminders.exists():
                    self.stdout.write(self.style.WARNING(f"Found {due_reminders.count()} due reminders at {now}"))
                    
                    for reminder in due_reminders:
                        user = reminder.user
                        recipient = user.email
                        
                        if recipient:
                            self.stdout.write(self.style.SUCCESS(
                                f"Sending real email notification to {recipient} for '{reminder.title}'"
                            ))
                            
                            # Send real email notification via SMTP
                            send_mail(
                                subject=f"Reminder: {reminder.title}",
                                message=(
                                    f"Hello {user.username},\n\n"
                                    f"This is a scheduled reminder from Recallify:\n\n"
                                    f"Event: {reminder.title}\n"
                                    f"Scheduled Time: {reminder.scheduled_time.strftime('%Y-%m-%d %I:%M %p')}\n"
                                    f"Description: {reminder.description or 'No description provided.'}\n\n"
                                    f"Best regards,\nRecallify Automated Scheduler"
                                ),
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[recipient],
                                fail_silently=False
                            )
                        else:
                            self.stdout.write(self.style.ERROR(
                                f"User {user.username} has no email registered. Skipping SMTP mail."
                            ))
                        
                        # Update status to 'sent'
                        reminder.status = 'sent'
                        reminder.save()
                        
                        # Create ActivityLog entry
                        ActivityLog.objects.create(
                            user=user,
                            action_type='Reminder Notification Sent',
                            details=f"Real email notification dispatched for reminder: '{reminder.title}' scheduled for {reminder.scheduled_time}."
                        )
                
                # Check for due reminders every 10 seconds
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS('Scheduler stopped by user.'))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in scheduler: {str(e)}"))
                time.sleep(10)
