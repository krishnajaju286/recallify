from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free Tier'),
        ('premium', 'Premium Tier'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='free')
    reminder_limit = models.IntegerField(default=10) # Max active reminders for free tier
    
    # Premium Billing / Admin requirements
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    premium_opted_at = models.DateTimeField(blank=True, null=True)
    premium_expires_at = models.DateTimeField(blank=True, null=True)
    payment_method = models.CharField(max_length=50, default='Credit Card', blank=True, null=True)
    card_details = models.CharField(max_length=50, default='Visa ending in 4242', blank=True, null=True)
    expiry_warning_sent = models.BooleanField(default=False)
    offer_sent = models.BooleanField(default=False)
    timezone = models.CharField(max_length=100, default='Asia/Kolkata')
    last_login_ip = models.CharField(max_length=50, blank=True, null=True)
    last_active_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s profile ({self.get_subscription_tier_display()})"

class Reminder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('upcoming', 'Upcoming'),
        ('confirmed', 'Confirmed'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    SOURCE_CHOICES = [
        ('Dashboard', 'Dashboard'),
        ('Email', 'Email'),
        ('Upcoming', 'Upcoming'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    scheduled_time = models.DateTimeField()
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default='Dashboard')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    raw_email_body = models.TextField(blank=True, null=True) # To store original text if created via email
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_time']

    def __str__(self):
        return f"{self.title} - {self.scheduled_time} ({self.status})"

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action_type = models.CharField(max_length=100) # e.g., 'Created Reminder', 'Triggered Reminder', 'Updated Subscription'
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action_type} at {self.timestamp}"

# Django Signals to auto-create user profile
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        UserProfile.objects.create(user=instance)

