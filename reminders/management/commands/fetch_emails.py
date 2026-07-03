import imaplib
import email
from email.header import decode_header
import re
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from reminders.models import Reminder, ActivityLog
from reminders.email_parser import parse_email_reminder

class Command(BaseCommand):
    help = 'Fetches incoming email reminders from the Gmail inbox and parses them.'

    def handle(self, *args, **options):
        # 1. Check if passwords are configured
        if getattr(settings, 'IMAP_PASSWORD', '') == 'your-gmail-app-password-here' or getattr(settings, 'EMAIL_HOST_PASSWORD', '') == 'your-gmail-app-password-here':
            self.stdout.write(self.style.WARNING(
                "\n============================================================\n"
                "WARNING: Gmail App Password placeholder detected in settings.py!\n"
                "Please configure 'IMAP_PASSWORD' and 'EMAIL_HOST_PASSWORD'\n"
                "with your 16-character Google App Password to enable real email polling.\n"
                "============================================================\n"
            ))
            return

        self.stdout.write(self.style.SUCCESS("Connecting to IMAP server..."))
        
        try:
            # 2. Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL(settings.IMAP_SERVER, settings.IMAP_PORT)
            mail.login(settings.IMAP_EMAIL, settings.IMAP_PASSWORD)
            mail.select("inbox")
            
            # 3. Search for unseen emails
            status, messages = mail.search(None, 'UNSEEN')
            
            if status != 'OK':
                self.stdout.write(self.style.ERROR("Failed to search unread emails."))
                return
                
            email_ids = messages[0].split()
            if not email_ids:
                self.stdout.write(self.style.SUCCESS("No new unread emails found."))
                mail.logout()
                return
                
            self.stdout.write(self.style.SUCCESS(f"Found {len(email_ids)} unread email(s) to process."))
            
            for mail_id in email_ids:
                status, data = mail.fetch(mail_id, '(RFC822)')
                if status != 'OK':
                    self.stdout.write(self.style.ERROR(f"Failed to fetch email ID {mail_id}"))
                    continue
                    
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # 4. Parse Header (Subject & Sender)
                subject, encoding = decode_header(msg["Subject"] or "")[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")
                    
                sender = msg["From"] or ""
                # Extract clean email address using regex
                sender_match = re.search(r'<([^>]+)>', sender)
                sender_email = sender_match.group(1).strip() if sender_match else sender.strip()
                
                # 5. Extract Body (Plain Text)
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            try:
                                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                break
                            except Exception:
                                pass
                else:
                    try:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                
                subject = subject.strip()
                body = body.strip()
                
                self.stdout.write(self.style.WARNING(f"\nProcessing email from: {sender_email}"))
                self.stdout.write(self.style.WARNING(f"Subject: {subject}"))
                
                # 6. Locate User in Database
                user = User.objects.filter(email=sender_email).first()
                if not user:
                    self.stdout.write(self.style.ERROR(f"Sender '{sender_email}' is not a registered user. Ignoring email."))
                    # Mark as read anyway so we don't loop on it
                    mail.store(mail_id, '+FLAGS', '\\Seen')
                    continue
                
                # 7. Check if this is a Yes/No response to a pending reminder
                clean_body = body.lower().strip()
                clean_subject = subject.lower().strip()
                
                is_yes = clean_body == 'yes' or clean_subject == 'yes'
                is_no = clean_body == 'no' or clean_subject == 'no'
                
                if is_yes or is_no:
                    # Find the latest pending reminder for this user
                    pending_reminder = Reminder.objects.filter(user=user, status='pending').order_by('-created_at').first()
                    if pending_reminder:
                        if is_yes:
                            pending_reminder.status = 'confirmed'
                            pending_reminder.save()
                            
                            ActivityLog.objects.create(
                                user=user,
                                action_type='Email Confirmation Received',
                                details=f"User replied YES via email. Confirmed reminder: '{pending_reminder.title}'."
                            )
                            
                            # Send real confirmation notification
                            send_mail(
                                subject=f"Scheduled: {pending_reminder.title}",
                                message=(
                                    f"Hello {user.username},\n\n"
                                    f"Thank you! Your reminder '{pending_reminder.title}' has been successfully confirmed and scheduled.\n"
                                    f"Date & Time: {pending_reminder.scheduled_time.strftime('%Y-%m-%d %I:%M %p')}\n\n"
                                    f"Best regards,\nRecallify Automated Scheduler"
                                ),
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[sender_email],
                                fail_silently=True
                            )
                            self.stdout.write(self.style.SUCCESS(f"Confirmed pending reminder: '{pending_reminder.title}'"))
                        else:
                            pending_reminder.status = 'failed'
                            pending_reminder.save()
                            
                            ActivityLog.objects.create(
                                user=user,
                                action_type='Email Confirmation Received',
                                details=f"User replied NO via email. Cancelled reminder: '{pending_reminder.title}'."
                            )
                            
                            # Send cancellation confirmation
                            send_mail(
                                subject=f"Cancelled: {pending_reminder.title}",
                                message=(
                                    f"Hello {user.username},\n\n"
                                    f"We have cancelled your reminder request for '{pending_reminder.title}' as requested.\n\n"
                                    f"Best regards,\nRecallify Automated Scheduler"
                                ),
                                from_email=settings.EMAIL_HOST_USER,
                                recipient_list=[sender_email],
                                fail_silently=True
                            )
                            self.stdout.write(self.style.SUCCESS(f"Cancelled pending reminder: '{pending_reminder.title}'"))
                    else:
                        self.stdout.write(self.style.ERROR("Yes/No response received but no pending reminder exists."))
                        
                    # Mark as read
                    mail.store(mail_id, '+FLAGS', '\\Seen')
                    continue
                
                # 8. Regular email reminder parsing
                # Check reminder limits for free users
                profile = user.profile
                if profile.subscription_tier == 'free':
                    active_count = Reminder.objects.filter(user=user, status__in=['pending', 'upcoming', 'confirmed']).count()
                    if active_count >= profile.reminder_limit:
                        self.stdout.write(self.style.ERROR(f"User {user.username} has reached reminder limit (10). Rejecting email."))
                        send_mail(
                            subject="Recallify - Reminder Limit Reached",
                            message=(
                                f"Hello {user.username},\n\n"
                                f"You have reached your Free Tier reminder limit (10 active reminders).\n"
                                f"Upgrade to Premium on the Recallify Web Dashboard for unlimited reminder creation.\n\n"
                                f"Best regards,\nRecallify Automated Scheduler"
                            ),
                            from_email=settings.EMAIL_HOST_USER,
                            recipient_list=[sender_email],
                            fail_silently=True
                        )
                        mail.store(mail_id, '+FLAGS', '\\Seen')
                        continue
                
                parsed_data = parse_email_reminder(subject, body)
                
                # Check for am/pm or designated time omissions
                combined_text = f"{subject} {body}".lower()
                has_ampm = 'am' in combined_text or 'pm' in combined_text
                
                time_pattern = r'(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))'
                has_designated_time = bool(re.search(time_pattern, combined_text))
                
                needs_confirmation = not has_ampm or not has_designated_time
                
                if needs_confirmation:
                    # Save as pending status
                    reminder = Reminder.objects.create(
                        user=user,
                        title=parsed_data['title'],
                        description=parsed_data['description'],
                        scheduled_time=parsed_data['scheduled_time'],
                        source='Email',
                        status='pending',
                        raw_email_body=f"Subject: {subject}\n\n{body}"
                    )
                    
                    ActivityLog.objects.create(
                        user=user,
                        action_type='Confirmation Request Sent',
                        details=f"Omission detected in email time details. Sent confirmation request for '{reminder.title}' (scheduled: {reminder.scheduled_time}). Waiting for email response."
                    )
                    
                    # Send real email asking for confirmation
                    send_mail(
                        subject=f"Confirmation Required: {reminder.title}",
                        message=(
                            f"Hello {user.username},\n\n"
                            f"We received your email schedule request: '{reminder.title}'.\n"
                            f"Because there was no explicit AM/PM or designated time details, "
                            f"we have tentatively scheduled this for:\n"
                            f"Date & Time: {reminder.scheduled_time.strftime('%Y-%m-%d %I:%M %p')}\n\n"
                            f"Please reply directly to this email with either 'Yes' or 'No' to confirm or cancel this reminder.\n\n"
                            f"Best regards,\nRecallify Automated Scheduler"
                        ),
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[sender_email],
                        fail_silently=True
                    )
                    self.stdout.write(self.style.SUCCESS(f"Saved pending reminder and dispatched confirmation email for: '{reminder.title}'"))
                else:
                    # Save as confirmed status directly
                    reminder = Reminder.objects.create(
                        user=user,
                        title=parsed_data['title'],
                        description=parsed_data['description'],
                        scheduled_time=parsed_data['scheduled_time'],
                        source='Email',
                        status='confirmed',
                        raw_email_body=f"Subject: {subject}\n\n{body}"
                    )
                    
                    ActivityLog.objects.create(
                        user=user,
                        action_type='Created Reminder via Email',
                        details=f"Email received & parsed. Created reminder: '{reminder.title}' scheduled for {reminder.scheduled_time}."
                    )
                    
                    # Send real success notification
                    send_mail(
                        subject=f"Scheduled: {reminder.title}",
                        message=(
                            f"Hello {user.username},\n\n"
                            f"Your email reminder has been successfully received and scheduled!\n"
                            f"Event: {reminder.title}\n"
                            f"Scheduled Time: {reminder.scheduled_time.strftime('%Y-%m-%d %I:%M %p')}\n\n"
                            f"Best regards,\nRecallify Automated Scheduler"
                        ),
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[sender_email],
                        fail_silently=True
                    )
                    self.stdout.write(self.style.SUCCESS(f"Created confirmed reminder: '{reminder.title}'"))
                
                # Mark email as read on server
                mail.store(mail_id, '+FLAGS', '\\Seen')
            
            mail.logout()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Connection failed: {str(e)}"))
