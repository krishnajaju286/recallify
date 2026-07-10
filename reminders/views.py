from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from .models import Reminder, ActivityLog, UserProfile
from .forms import ReminderForm, EmailSimForm, UserSignupForm
from .email_parser import parse_email_reminder


import urllib.request
import datetime

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_timezone_from_ip(ip_address):
    if not ip_address or ip_address in ['127.0.0.1', '::1', 'localhost']:
        return 'Asia/Kolkata'
    try:
        url = f'https://ipapi.co/{ip_address}/timezone/'
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                tz = response.read().decode('utf-8').strip()
                import zoneinfo
                if tz in zoneinfo.available_timezones():
                    return tz
    except Exception:
        pass
    return 'Asia/Kolkata'

def seed_user_reminders(user):
    now = timezone.now()
    
    # 1. Doctor's Appointment (Tomorrow at 2:00 PM)
    tomorrow = now + datetime.timedelta(days=1)
    doc_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    Reminder.objects.create(
        user=user,
        title="Doctor's Appointment",
        scheduled_time=doc_time,
        source='Email',
        status='pending'
    )
    
    # 2. Project Deadline (Next Friday at 6:00 PM)
    days_to_friday = (4 - now.weekday()) % 7
    if days_to_friday == 0:
        days_to_friday = 7
    friday = now + datetime.timedelta(days=days_to_friday)
    deadline_time = friday.replace(hour=18, minute=0, second=0, microsecond=0)
    Reminder.objects.create(
        user=user,
        title="Project Deadline",
        description="Project deadline, in description, detailed plans compress to the description of find confirmation and qualify details.",
        scheduled_time=deadline_time,
        source='Email',
        status='confirmed'
    )
    
    # 3. Birthday Party (Later today at 7:00 PM)
    party_time = now.replace(hour=19, minute=0, second=0, microsecond=0)
    if party_time < now:
        party_time += datetime.timedelta(days=1)
    Reminder.objects.create(
        user=user,
        title="Birthday Party",
        scheduled_time=party_time,
        source='Upcoming',
        status='upcoming'
    )
    
    # 4. Team Meeting (Next Monday at 10:00 AM)
    days_to_monday = (0 - now.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    monday = now + datetime.timedelta(days=days_to_monday)
    meeting_time = monday.replace(hour=10, minute=0, second=0, microsecond=0)
    Reminder.objects.create(
        user=user,
        title="Team Meeting",
        scheduled_time=meeting_time,
        source='Email',
        status='pending'
    )

# Custom signup view
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            # Seed demo reminders to match mock design
            try:
                seed_user_reminders(user)
            except Exception:
                pass
            # Log user in
            login(request, user)
            
            # Resolve default timezone by signup IP location
            try:
                profile = user.profile
                ip = get_client_ip(request)
                located_tz = get_timezone_from_ip(ip)
                profile.timezone = located_tz
                profile.last_login_ip = ip
                profile.save()
            except Exception:
                pass
                
            messages.success(request, f"Welcome to Recallify, {user.username}!")
            # Log action
            ActivityLog.objects.create(
                user=user,
                action_type='Account Created',
                details=f"Signed up and completed onboarding. IP Timezone resolved to {profile.timezone}."
            )
            return redirect('dashboard')
    else:
        form = UserSignupForm()
    return render(request, 'reminders/signup.html', {'form': form})

# Custom login view
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            
            # Set default timezone if not already customized
            profile = user.profile
            try:
                ip = get_client_ip(request)
                profile.last_login_ip = ip
                if profile.timezone == 'Asia/Kolkata':
                    located_tz = get_timezone_from_ip(ip)
                    if located_tz != profile.timezone:
                        profile.timezone = located_tz
                profile.save()
            except Exception:
                pass
                    
            messages.success(request, f"Welcome back, {user.username}!")
            ActivityLog.objects.create(
                user=user,
                action_type='Login',
                details=f"Logged in successfully. Resolved timezone: {profile.timezone}."
            )
            try:
                from django.core.management import call_command
                call_command('fetch_emails')
            except Exception as e:
                print(f"Error fetching emails on login redirect: {e}")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'reminders/login.html')

# Logout view
def logout_view(request):
    if request.user.is_authenticated:
        ActivityLog.objects.create(
            user=request.user,
            action_type='Logout',
            details='Logged out successfully.'
        )
        logout(request)
    return redirect('landing')

# Dashboard: List upcoming events and manage them
@login_required
def dashboard_view(request):
    try:
        from django.core.management import call_command
        call_command('fetch_emails')
    except Exception as e:
        print(f"Error fetching emails on dashboard load: {e}")

    query = request.GET.get('search', '')
    
    if request.user.is_superuser:
        return redirect('admin_dashboard')

    # Filter by user and optional search
    reminders = Reminder.objects.filter(user=request.user)
    if query:
        reminders = reminders.filter(title__icontains=query) | reminders.filter(description__icontains=query)
    
    # Sort active/upcoming reminders (exclude already sent or failed for main dashboard view, or show all depending on status)
    # The reference image shows overall events, some are confirmed, upcoming, etc. Let's show upcoming, confirmed, and triggered ones.
    # We will exclude 'sent' and 'failed' from the main dashboard list to only show active reminders, or show everything that isn't fully processed.
    # In the reference image, it has: "Doctor's Appointment" (Upcoming), "Project Deadline" (Confirmed), "Birthday Party" (Upcoming), etc.
    # Let's show all pending/upcoming/confirmed reminders.
    active_reminders = reminders.filter(status__in=['pending', 'upcoming', 'confirmed']).order_by('scheduled_time')
    
    # Calculate stats
    total_reminders = reminders.count()
    sent_reminders = reminders.filter(status='sent').count()
    pending_reminders = active_reminders.count()
    
    # Fetch user directory details for superusers
    users_list = None
    if request.user.is_superuser:
        users_list = list(User.objects.all().select_related('profile').prefetch_related('reminders').order_by('username'))
        for u in users_list:
            u.pending_count = u.reminders.filter(status__in=['pending', 'upcoming', 'confirmed']).count()
            u.total_count = u.reminders.count()
    
    # Calculate first name of the user
    user = request.user
    if user.first_name:
        first_name = user.first_name.strip().split()[0].capitalize()
    else:
        import re
        name_part = re.split(r'[-_\s\d]+', user.username)[0]
        first_name = name_part.capitalize() if name_part else user.username.capitalize()

    # Calculate interactive dashboard heading based on the most recent upcoming event
    next_event = active_reminders.filter(scheduled_time__gt=timezone.now()).order_by('scheduled_time').first()
    
    if next_event:
        title_lower = next_event.title.lower()
        
        if any(kw in title_lower for kw in ["date", "girlfriend", "boyfriend", "romantic"]):
            greeting = f"Excited for the day, {first_name}!"
        elif any(kw in title_lower for kw in ["flight", "travel", "trip", "vacation", "airport"]):
            greeting = f"Ready to take off, {first_name}?"
        elif any(kw in title_lower for kw in ["interview", "exam", "presentation", "test"]):
            greeting = f"Feeling nervous for the interview, {first_name}?"
        elif any(kw in title_lower for kw in ["doctor", "dentist", "medical", "checkup"]):
            greeting = f"Time for your health checkup, {first_name}!"
        elif any(kw in title_lower for kw in ["gym", "workout", "jogging", "run", "exercise"]):
            greeting = f"Ready to break a sweat, {first_name}?"
        elif any(kw in title_lower for kw in ["grocery", "groceries", "shopping", "buy"]):
            greeting = f"Time to check off your shopping list, {first_name}!"
        elif any(kw in title_lower for kw in ["meeting", "sync", "standup", "call", "work"]):
            greeting = f"Ready to sync up, {first_name}?"
        elif any(kw in title_lower for kw in ["birthday", "party", "anniversary", "celebrate"]):
            greeting = f"Ready to celebrate, {first_name}?"
        elif any(kw in title_lower for kw in ["movie", "concert", "show", "play"]):
            greeting = f"Enjoy the show, {first_name}!"
        else:
            greeting = f"Next event: '{next_event.title}', {first_name}!"
    else:
        # Choose a creative regional/interactive greeting when schedule is clear
        import random
        greetings_pool = ["Namaste", "Hello", "Vanakkam", "Hey there", "Adaab", "Hi"]
        selected_prefix = random.choice(greetings_pool)
        greeting = f"{selected_prefix}, {first_name}!"

    context = {
        'reminders': active_reminders,
        'total_reminders': total_reminders,
        'sent_reminders': sent_reminders,
        'pending_reminders': pending_reminders,
        'search_query': query,
        'current_time': timezone.now(),
        'page': 'dashboard',
        'users_list': users_list,
        'dashboard_heading': greeting
    }
    return render(request, 'reminders/dashboard.html', context)

# Create reminder manually
@login_required
def create_reminder(request):
    profile = request.user.profile
    # Check limit for free tier
    if profile.subscription_tier == 'free':
        active_count = Reminder.objects.filter(user=request.user, status__in=['pending', 'upcoming', 'confirmed']).count()
        if active_count >= profile.reminder_limit:
            messages.warning(request, "You have reached your Free Tier reminder limit (10). Upgrade to Premium for unlimited reminders!")
            return redirect('subscription')

    if request.method == 'POST':
        form = ReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.user = request.user
            # For dashboard creation, we assign 'Dashboard' source and status 'upcoming' or 'confirmed'
            # In the reference image: "Birthday Party" has source "Upcoming" and status "Upcoming". Let's support this.
            reminder.source = 'Upcoming'
            reminder.status = 'upcoming'
            
            # Auto-format description with AI-intelligence bullets
            from reminders.email_parser import generate_bulleted_description
            reminder.description = generate_bulleted_description(reminder.title, reminder.description, reminder.scheduled_time)
            
            reminder.save()
            
            ActivityLog.objects.create(
                user=request.user,
                action_type='Created Reminder',
                details=f"Created reminder: '{reminder.title}' via Web Dashboard."
            )
            messages.success(request, f"Reminder '{reminder.title}' scheduled successfully!")
            return redirect('dashboard')
    else:
        form = ReminderForm()
    
    return render(request, 'reminders/create_reminder.html', {'form': form, 'page': 'create'})

# Email Simulator
@login_required
def email_sim_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        import re
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        clean_body = body.lower().strip().strip(',.?!;:-')
        clean_subject = subject.lower().strip()
        
        # Check if there is an active pending reminder for this user
        pending_reminder = Reminder.objects.filter(user=request.user, status='pending').order_by('-created_at').first()
        is_no = bool(re.match(r'^(no|cancel|n\b)', clean_body)) or clean_subject == 'no'
        
        if pending_reminder:
            if is_no:
                pending_reminder.status = 'failed'
                pending_reminder.save()
                ActivityLog.objects.create(
                    user=request.user,
                    action_type='Email Confirmation Received',
                    details=f"User replied NO. Cancelled/Failed reminder: '{pending_reminder.title}'."
                )
                messages.warning(request, f"Confirmation received! Reminder '{pending_reminder.title}' has been CANCELLED.")
            else:
                # User confirmed or updated details
                reply_has_explicit_ampm = bool(re.search(r'\b\d{1,2}(?::\d{2})?\s*(am|pm)\b', clean_body))
                reply_has_explicit_24h = bool(re.search(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b', clean_body))
                reply_has_ambiguous_time = bool(re.search(r'\b(?:at|around|@|by)\s*\d{1,2}(?::\d{2})?\b', clean_body))
                reply_has_time = reply_has_explicit_ampm or reply_has_explicit_24h or reply_has_ambiguous_time
                
                reply_has_date = any(kw in clean_body for kw in [
                    "tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "weekend"
                ]) or bool(re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})', clean_body))
                
                action_details = f"User confirmed pending reminder via simulator: '{pending_reminder.title}'."
                
                if reply_has_time or reply_has_date:
                    parsed_reply = parse_email_reminder(subject, body)
                    
                    current_dt = timezone.make_naive(pending_reminder.scheduled_time, timezone.get_current_timezone())
                    parsed_dt = timezone.make_naive(parsed_reply['scheduled_time'], timezone.get_current_timezone())
                    
                    new_date = parsed_dt.date() if reply_has_date else current_dt.date()
                    new_time = parsed_dt.time() if reply_has_time else current_dt.time()
                    
                    new_datetime = datetime.datetime.combine(new_date, new_time)
                    pending_reminder.scheduled_time = timezone.make_aware(new_datetime, timezone.get_current_timezone())
                    
                    parsed_title = parsed_reply['title']
                    if parsed_title and parsed_title.lower() not in ["email reminder", "yes", "confirm", "y"]:
                        pending_reminder.title = parsed_title
                        
                    action_details = f"User confirmed with changes via simulator: '{pending_reminder.title}' (scheduled: {pending_reminder.scheduled_time})."
                    
                pending_reminder.status = 'confirmed'
                pending_reminder.save()
                
                ActivityLog.objects.create(
                    user=request.user,
                    action_type='Email Confirmation Received',
                    details=action_details
                )
                messages.success(request, f"Confirmation received! Reminder '{pending_reminder.title}' is now CONFIRMED.")
            return redirect('dashboard')
        
        # 2. Regular reminder parsing
        # Check limit
        if profile.subscription_tier == 'free':
            active_count = Reminder.objects.filter(user=request.user, status__in=['pending', 'upcoming', 'confirmed']).count()
            if active_count >= profile.reminder_limit:
                messages.warning(request, "Limit reached! Upgrade to Premium to add more reminders.")
                return redirect('subscription')
        
        # Parse simulated email
        parsed_data = parse_email_reminder(subject, body)
        
        # Check for explicit AM/PM or strictly 24-hour style format
        combined_text = f"{subject} {body}".lower()
        has_explicit_ampm = bool(re.search(r'\b\d{1,2}(?::\d{2})?\s*(am|pm)\b', combined_text))
        has_explicit_24h = bool(re.search(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b', combined_text))
        
        needs_confirmation = not (has_explicit_ampm or has_explicit_24h)
        
        if needs_confirmation:
            # Create reminder in PENDING status
            reminder = Reminder.objects.create(
                user=request.user,
                title=parsed_data['title'],
                description=parsed_data['description'],
                scheduled_time=parsed_data['scheduled_time'],
                source='Email',
                status='pending',
                raw_email_body=f"Subject: {subject}\n\n{body}"
            )
            
            # Log system action
            ActivityLog.objects.create(
                user=request.user,
                action_type='Confirmation Request Sent',
                details=f"Omission detected in email time details. Sent confirmation request for '{reminder.title}' (scheduled: {reminder.scheduled_time}). Waiting for user reply."
            )
            
            # Alert user via UI messages
            messages.warning(
                request, 
                f"We noticed that your email lacks an explicit AM/PM or a designated time! "
                f"A confirmation request has been sent to {request.user.email}. "
                f"Please reply 'Yes' or 'No' in this simulator to confirm or cancel the schedule."
            )
            return redirect('email_simulator')
            
        else:
            # Create reminder in CONFIRMED status directly
            reminder = Reminder.objects.create(
                user=request.user,
                title=parsed_data['title'],
                description=parsed_data['description'],
                scheduled_time=parsed_data['scheduled_time'],
                source='Email',
                status='confirmed',
                raw_email_body=f"Subject: {subject}\n\n{body}"
            )
            
            # Log action
            ActivityLog.objects.create(
                user=request.user,
                action_type='Created Reminder via Email',
                details=f"Email received & parsed. Created reminder: '{reminder.title}' scheduled for {reminder.scheduled_time}."
            )
            
            messages.success(request, f"Email received! Successfully parsed and scheduled reminder: '{reminder.title}'")
            return redirect('dashboard')
    else:
        form = EmailSimForm(initial={'sender_email': request.user.email or f"{request.user.username}@example.com"})
    
    return render(request, 'reminders/email_sim.html', {'form': form, 'page': 'email_sim'})

# Edit Reminder
@login_required
def edit_reminder(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ReminderForm(request.POST, instance=reminder)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.status = 'confirmed'
            
            # Auto-format description with AI-intelligence bullets
            from reminders.email_parser import generate_bulleted_description
            reminder.description = generate_bulleted_description(reminder.title, reminder.description, reminder.scheduled_time)
            
            reminder.save()
            ActivityLog.objects.create(
                user=request.user,
                action_type='Updated Reminder',
                details=f"Modified reminder ID {reminder.id}: '{reminder.title}'."
            )
            messages.success(request, "Reminder updated successfully!")
            return redirect('dashboard')
    else:
        form = ReminderForm(instance=reminder)
    return render(request, 'reminders/edit_reminder.html', {'form': form, 'reminder': reminder})

# Delete Reminder
@login_required
def delete_reminder(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, user=request.user)
    title = reminder.title
    reminder.delete()
    ActivityLog.objects.create(
        user=request.user,
        action_type='Deleted Reminder',
        details=f"Deleted reminder: '{title}'."
    )
    messages.success(request, f"Reminder '{title}' deleted successfully.")
    return redirect('dashboard')

# History / logs page
@login_required
def history_view(request):
    # Logs and sent reminders
    history_reminders = Reminder.objects.filter(user=request.user, status__in=['sent', 'failed']).order_by('-scheduled_time')
    logs = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')
    
    context = {
        'history_reminders': history_reminders,
        'logs': logs,
        'page': 'history'
    }
    return render(request, 'reminders/logs.html', context)

# Subscription Management
@login_required
def subscription_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        tier = request.POST.get('tier')
        if tier == 'free':
            profile.subscription_tier = 'free'
            profile.premium_opted_at = None
            profile.premium_expires_at = None
            profile.save()
            ActivityLog.objects.create(
                user=request.user,
                action_type='Updated Subscription',
                details="Changed subscription tier to FREE."
            )
            messages.success(request, "Successfully switched to the FREE subscription tier!")
            return redirect('subscription')
        elif tier == 'premium':
            messages.error(request, "Direct upgrade is disabled. Please use the secure checkout portal.")
            return redirect('checkout')
            
    active_count = Reminder.objects.filter(user=request.user, status__in=['pending', 'upcoming', 'confirmed']).count()
    context = {
        'profile': profile,
        'active_count': active_count,
        'page': 'subscription'
    }
    return render(request, 'reminders/subscription.html', context)

@login_required
def checkout_view(request):
    profile = request.user.profile
    if profile.subscription_tier == 'premium':
        messages.info(request, "You are already a Premium subscriber.")
        return redirect('subscription')
        
    if request.method == 'POST':
        cardholder = request.POST.get('cardholder_name', '').strip()
        card_number = request.POST.get('card_number', '').replace(' ', '')
        expiry = request.POST.get('expiry_date', '').strip()
        cvv = request.POST.get('cvv', '').strip()
        
        if not (cardholder and card_number.isdigit() and len(card_number) >= 15 and len(cvv) >= 3):
            messages.error(request, "Payment failed. Please verify your card credentials and try again.")
            return render(request, 'reminders/checkout.html', {'profile': profile, 'page': 'subscription'})
            
        now = timezone.now()
        profile.subscription_tier = 'premium'
        profile.premium_opted_at = now
        profile.premium_expires_at = now + timedelta(days=365)
        profile.payment_method = 'Credit Card'
        
        last_four = card_number[-4:]
        card_brand = "Visa"
        if card_number.startswith('5'):
            card_brand = "Mastercard"
        elif card_number.startswith('3'):
            card_brand = "American Express"
            
        profile.card_details = f"{card_brand} ending in {last_four}"
        profile.expiry_warning_sent = False
        profile.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action_type='Payment Processed',
            details=f"Processed payment for monthly premium. Card: {profile.card_details}."
        )
        
        messages.success(request, "Payment processed successfully! Welcome to Recallify Premium.")
        return redirect('dashboard')
        
    return render(request, 'reminders/checkout.html', {'profile': profile, 'page': 'subscription'})

@login_required
def settings_view(request):
    profile = request.user.profile
    import zoneinfo
    if request.method == 'POST':
        selected_tz = request.POST.get('timezone', '').strip()
        if selected_tz in zoneinfo.available_timezones():
            old_tz = profile.timezone
            profile.timezone = selected_tz
            profile.save()
            
            ActivityLog.objects.create(
                user=request.user,
                action_type='Updated Timezone',
                details=f"Changed timezone configuration from {old_tz} to {selected_tz}."
            )
            messages.success(request, f"Preferred timezone successfully updated to {selected_tz}!")
            return redirect('settings')
        else:
            messages.error(request, "Invalid timezone selection.")
            
    all_timezones = sorted(zoneinfo.available_timezones())
    context = {
        'profile': profile,
        'page': 'settings',
        'timezones': all_timezones
    }
    return render(request, 'reminders/settings.html', context)

def landing_view(request):
    return render(request, 'reminders/landing.html')

@login_required
def confirm_pending_reminder(request, pk):
    reminder = get_object_or_404(Reminder, id=pk, user=request.user)
    if request.method == 'POST':
        title = request.POST.get('title')
        scheduled_time_str = request.POST.get('scheduled_time')
        action = request.POST.get('action')  # 'confirm' or 'save'
        
        if title:
            reminder.title = title
        if scheduled_time_str:
            try:
                from django.utils.dateparse import parse_datetime
                naive_dt = parse_datetime(scheduled_time_str)
                if naive_dt:
                    from django.utils.timezone import get_current_timezone, make_aware
                    tz = get_current_timezone()
                    reminder.scheduled_time = make_aware(naive_dt, tz)
            except Exception as e:
                messages.error(request, f"Error parsing scheduled time: {e}")
                return redirect('dashboard')
                
        if action == 'confirm':
            reminder.status = 'confirmed'
            messages.success(request, f"Reminder '{reminder.title}' has been confirmed and scheduled!")
            ActivityLog.objects.create(
                user=request.user,
                action_type='Reminder Confirmed',
                details=f"Manually confirmed reminder '{reminder.title}' via inline dashboard modal."
            )
        else:
            messages.success(request, f"Reminder '{reminder.title}' details updated.")
            ActivityLog.objects.create(
                user=request.user,
                action_type='Reminder Edited',
                details=f"Edited pending reminder details for '{reminder.title}'."
            )
        reminder.save()
    return redirect('dashboard')

from datetime import timedelta
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

@login_required
def admin_upgrade_user(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Permission denied.")
        return redirect('dashboard')
        
    u = get_object_or_404(User, id=user_id)
    profile = u.profile
    
    if request.method == 'POST':
        duration_type = request.POST.get('duration_type')
        now = timezone.now()
        
        if duration_type == '1_month':
            expiry = now + timedelta(days=30)
            duration_desc = "1 Month"
        elif duration_type == '3_months':
            expiry = now + timedelta(days=90)
            duration_desc = "3 Months"
        elif duration_type == '6_months':
            expiry = now + timedelta(days=180)
            duration_desc = "6 Months"
        elif duration_type == '1_year':
            expiry = now + timedelta(days=365)
            duration_desc = "1 Year"
        else:
            try:
                custom_days = int(request.POST.get('custom_days', 30))
            except ValueError:
                custom_days = 30
            expiry = now + timedelta(days=custom_days)
            duration_desc = f"{custom_days} Days"
            
        profile.subscription_tier = 'premium'
        profile.premium_opted_at = now
        profile.premium_expires_at = expiry
        profile.payment_method = 'Admin Manual Override'
        profile.card_details = 'No Card (Admin Upgraded)'
        profile.expiry_warning_sent = False
        profile.save()
        
        ActivityLog.objects.create(
            user=request.user,
            action_type='Admin Upgraded User',
            details=f"Upgraded {u.username} to Premium Tier for {duration_desc}."
        )
        
        send_mail(
            subject="Recallify - Account Upgraded to Premium",
            message=(
                f"Hello {u.username},\n\n"
                f"Your Recallify account has been upgraded to Premium Tier by the Administrator!\n"
                f"Opted on: {now.strftime('%Y-%m-%d %I:%M %p')}\n"
                f"Expires on: {expiry.strftime('%Y-%m-%d %I:%M %p')}\n\n"
                f"Thank you for choosing Recallify!\nRecallify Automated Scheduler"
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[u.email],
            fail_silently=True
        )
        
        messages.success(request, f"Successfully upgraded {u.username} to Premium Tier for {duration_desc}!")
        
    return redirect('admin_dashboard')

@login_required
def admin_toggle_suspension(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Permission denied.")
        return redirect('dashboard')
        
    u = get_object_or_404(User, id=user_id)
    u.is_active = not u.is_active
    u.save()
    
    status_str = "Suspended" if not u.is_active else "Reactivated"
    
    ActivityLog.objects.create(
        user=request.user,
        action_type=f'Admin {status_str} User',
        details=f"Admin {status_str.lower()} account for {u.username}."
    )
    
    if not u.is_active:
        subject = "Recallify - Account Suspended"
        message = (
            f"Hello {u.username},\n\n"
            f"Your Recallify account has been temporarily suspended by the Administrator.\n"
            f"Please contact support if you believe this is an error.\n\n"
            f"Best regards,\nRecallify Automated Scheduler"
        )
    else:
        subject = "Recallify - Account Activated"
        message = (
            f"Hello {u.username},\n\n"
            f"Your Recallify account has been successfully reactivated by the Administrator.\n"
            f"You can now log in and continue using Recallify.\n\n"
            f"Best regards,\nRecallify Automated Scheduler"
        )
        
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[u.email],
        fail_silently=True
    )
    
    messages.success(request, f"Successfully {status_str.lower()} account for {u.username}!")
    return redirect('admin_dashboard')

@login_required
def admin_dashboard_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Permission denied.")
        return redirect('dashboard')
        
    query = request.GET.get('search', '')
    users = User.objects.all().select_related('profile').prefetch_related('reminders').order_by('username')
    if query:
        users = users.filter(username__icontains=query) | users.filter(email__icontains=query)
        
    users_data = []
    now = timezone.now()
    for u in users:
        if u.is_superuser:
            continue
        
        profile = getattr(u, 'profile', None)
        if not profile:
            profile = UserProfile.objects.create(user=u)
            
        sent_count = u.reminders.filter(status='sent').count()
        current_count = u.reminders.filter(status__in=['pending', 'upcoming', 'confirmed']).count()
        
        days_active = max(1, (now - u.date_joined).days)
        avg_daily = round(u.reminders.count() / days_active, 2)
        
        days_remaining = None
        if profile.subscription_tier == 'premium' and profile.premium_expires_at:
            days_remaining = max(0, (profile.premium_expires_at - now).days)
            
        is_online = False
        if profile.last_active_at:
            is_online = (now - profile.last_active_at).total_seconds() < 120
            
        users_data.append({
            'id': u.id,
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'full_name': f"{u.first_name} {u.last_name}".strip() or u.username,
            'email': u.email,
            'phone_number': profile.phone_number or 'N/A',
            'subscription_tier': profile.subscription_tier,
            'get_subscription_tier_display': profile.get_subscription_tier_display(),
            'sent_emails': sent_count,
            'current_reminders': current_count,
            'average_daily': avg_daily,
            'is_active': u.is_active,
            'premium_opted_at': profile.premium_opted_at,
            'premium_expires_at': profile.premium_expires_at,
            'payment_method': profile.payment_method,
            'card_details': profile.card_details,
            'days_remaining': days_remaining,
            'date_joined': u.date_joined,
            'is_online': is_online,
            'last_login_ip': profile.last_login_ip or 'N/A'
        })
        
    context = {
        'users_data': users_data,
        'search_query': query,
        'page': 'dashboard',
        'dashboard_heading': f"User Directory, {request.user.first_name or request.user.username}!"
    }
    return render(request, 'reminders/admin_dashboard.html', context)

@login_required
def admin_downgrade_user(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Permission denied.")
        return redirect('dashboard')
        
    u = get_object_or_404(User, id=user_id)
    profile = u.profile
    
    profile.subscription_tier = 'free'
    profile.premium_opted_at = None
    profile.premium_expires_at = None
    profile.reminder_limit = 10
    profile.save()
    
    ActivityLog.objects.create(
        user=request.user,
        action_type='Admin Downgraded User',
        details=f"Downgraded {u.username} to Free Tier."
    )
    
    send_mail(
        subject="Recallify - Account Downgraded to Basic Tier",
        message=(
            f"Hello {u.username},\n\n"
            f"Your Recallify account has been downgraded to the Basic (Free) Tier by the Administrator.\n"
            f"If you believe this is an error or wish to upgrade again, please visit the Dashboard.\n\n"
            f"Best regards,\nRecallify team"
        ),
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[u.email],
        fail_silently=True
    )
    
    messages.success(request, f"Successfully downgraded {u.username} to the Free Tier!")
    return redirect('admin_dashboard')

