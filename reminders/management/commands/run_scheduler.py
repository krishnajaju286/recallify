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
                            
                            scheduled_time_str = reminder.scheduled_time.strftime('%Y-%m-%d %I:%M %p')
                            description_text = reminder.description or 'No description provided.'
                            description_html = description_text.replace('\n', '<br>')

                            plain_message = (
                                f"Event- \"{reminder.title}\"\n"
                                f"time- \"{scheduled_time_str}\"\n\n"
                                f"description\n"
                                f"{description_text}\n\n"
                                f"-Recallify"
                            )

                            html_message = (
                                f"<div style=\"font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;\">"
                                f"  <p style=\"margin: 0 0 10px 0; font-size: 16px;\"><strong>Event-</strong> \"{reminder.title}\"</p>"
                                f"  <p style=\"margin: 0 0 20px 0; font-size: 16px;\"><strong>time-</strong> \"{scheduled_time_str}\"</p>"
                                f"  <p style=\"margin: 20px 0 10px 0; font-size: 16px; font-weight: bold;\">description</p>"
                                f"  <div style=\"font-size: 15px; color: #555; background-color: #f8fafc; padding: 15px; border-radius: 8px; margin-bottom: 25px;\">"
                                f"    {description_html}"
                                f"  </div>"
                                f"  <p style=\"margin: 20px 0 0 0; font-size: 15px; color: #666; font-weight: bold;\">-Recallify</p>"
                                f"</div>"
                            )

                            send_mail(
                                subject=f"Reminder: {reminder.title}",
                                message=plain_message,
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[recipient],
                                html_message=html_message,
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
                
                # Background Automated Billing Checks (Offer Promos & Expiry warnings)
                all_users = User.objects.all().select_related('profile').prefetch_related('reminders')
                for u in all_users:
                    if u.is_superuser:
                        continue
                    
                    profile = u.profile
                    # 1. Premium Expiry Warning Check (3 days prior)
                    if profile.subscription_tier == 'premium' and profile.premium_expires_at:
                        time_left = profile.premium_expires_at - now
                        if time_left <= timedelta(days=3) and not profile.expiry_warning_sent:
                            send_mail(
                                subject="Recallify - Your Premium Subscription is Expiring Soon",
                                message=(
                                    f"Hello {u.username},\n\n"
                                    f"This is a reminder that your Recallify Premium subscription is about to expire in 3 days on {profile.premium_expires_at.strftime('%Y-%m-%d')}.\n"
                                    f"Please renew your plan on the Dashboard to maintain unlimited reminders and advanced NLP features.\n\n"
                                    f"Best regards,\nRecallify team"
                                ),
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[u.email],
                                fail_silently=True
                            )
                            profile.expiry_warning_sent = True
                            profile.save()
                            
                    # 2. Free Avid/Loyal User Promo Check (avg daily > 5, today count >= 7, used 7 days straight, or member > 1 month)
                    elif profile.subscription_tier == 'free' and not profile.offer_sent:
                        days_active = max(1, (now - u.date_joined).days)
                        avg_daily = u.reminders.count() / days_active
                        today_count = u.reminders.filter(created_at__date=now.date()).count()
                        
                        # Check consecutive week activity logs
                        consecutive_days = 0
                        from reminders.models import ActivityLog
                        for i in range(7):
                            day_date = (now - timedelta(days=i)).date()
                            if ActivityLog.objects.filter(user=u, timestamp__date=day_date).exists():
                                consecutive_days += 1
                            else:
                                break
                        used_week_straight = (consecutive_days == 7)
                        been_user_over_month = (days_active > 30)
                        
                        qualifies = False
                        reason = ""
                        if avg_daily > 5 or today_count >= 7:
                            qualifies = True
                            reason = f"you are an avid user of Recallify (average of {avg_daily:.1f} reminders daily or {today_count} reminders today)"
                        elif used_week_straight:
                            qualifies = True
                            reason = "you have been using Recallify for a whole week straight"
                        elif been_user_over_month:
                            qualifies = True
                            reason = "you have been a loyal member of the Recallify community for over a month"
                            
                        if qualifies:
                            send_mail(
                                subject="Special Offer: Free Month of Recallify Premium!",
                                message=(
                                    f"Hello {u.username},\n\n"
                                    f"Since {reason}, we are offering you a month of free Premium Tier access!\n\n"
                                    f"We have set up an autopay subscription for the next 12 months starting after your free month.\n"
                                    f"To claim this offer or update your preferences, please check the Recallify Dashboard.\n\n"
                                    f"Best regards,\nRecallify team"
                                ),
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[u.email],
                                fail_silently=True
                            )
                            profile.offer_sent = True
                            profile.save()

                # Check for due reminders every 10 seconds
                time.sleep(10)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS('Scheduler stopped by user.'))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in scheduler: {str(e)}"))
                time.sleep(10)
