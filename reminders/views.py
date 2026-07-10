from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from .models import Reminder, ActivityLog, UserProfile
from .forms import ReminderForm, EmailSimForm, UserSignupForm
from .email_parser import parse_email_reminder


import datetime

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
            messages.success(request, f"Welcome to Recallify, {user.username}!")
            # Log action
            ActivityLog.objects.create(
                user=user,
                action_type='Account Created',
                details='Signed up and completed onboarding with seed data.'
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
            messages.success(request, f"Welcome back, {user.username}!")
            ActivityLog.objects.create(
                user=user,
                action_type='Login',
                details='Logged in successfully.'
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
    
    context = {
        'reminders': active_reminders,
        'total_reminders': total_reminders,
        'sent_reminders': sent_reminders,
        'pending_reminders': pending_reminders,
        'search_query': query,
        'current_time': timezone.now(),
        'page': 'dashboard',
        'users_list': users_list
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
        
        # 1. Check if this is a Yes/No response to a pending reminder
        clean_body = body.lower().strip().strip(',.?!;:-')
        clean_subject = subject.lower().strip()
        
        is_yes = bool(re.match(r'^(yes|confirm|y\b)', clean_body)) or clean_subject == 'yes'
        is_no = bool(re.match(r'^(no|cancel|n\b)', clean_body)) or clean_subject == 'no'
        
        if is_yes or is_no:
            # Find the most recent pending reminder for this user
            pending_reminder = Reminder.objects.filter(user=request.user, status='pending').order_by('-created_at').first()
            if pending_reminder:
                if is_yes:
                    pending_reminder.status = 'confirmed'
                    pending_reminder.save()
                    ActivityLog.objects.create(
                        user=request.user,
                        action_type='Email Confirmation Received',
                        details=f"User replied YES. Confirmed reminder: '{pending_reminder.title}' scheduled for {pending_reminder.scheduled_time}."
                    )
                    messages.success(request, f"Confirmation received! Reminder '{pending_reminder.title}' is now CONFIRMED.")
                else:
                    pending_reminder.status = 'failed'
                    pending_reminder.save()
                    ActivityLog.objects.create(
                        user=request.user,
                        action_type='Email Confirmation Received',
                        details=f"User replied NO. Cancelled/Failed reminder: '{pending_reminder.title}'."
                    )
                    messages.warning(request, f"Confirmation received! Reminder '{pending_reminder.title}' has been CANCELLED.")
                return redirect('dashboard')
            else:
                messages.warning(request, "No pending reminders requiring confirmation were found.")
                return redirect('email_simulator')
        
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
            form.save()
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
        if tier in ['free', 'premium']:
            profile.subscription_tier = tier
            profile.save()
            ActivityLog.objects.create(
                user=request.user,
                action_type='Updated Subscription',
                details=f"Changed subscription tier to {tier.upper()}."
            )
            messages.success(request, f"Successfully switched to the {tier.upper()} subscription tier!")
            return redirect('subscription')
            
    active_count = Reminder.objects.filter(user=request.user, status__in=['pending', 'upcoming', 'confirmed']).count()
    context = {
        'profile': profile,
        'active_count': active_count,
        'page': 'subscription'
    }
    return render(request, 'reminders/profile.html', context)

@login_required
def settings_view(request):
    profile = request.user.profile
    context = {
        'profile': profile,
        'page': 'settings'
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

