import re
import datetime
from django.utils import timezone

def parse_relative_date(date_str, now):
    """
    Parses terms like 'tomorrow', 'today', 'next friday', etc., and returns a date object.
    """
    date_str = date_str.lower().strip()
    
    # 1. Today
    if "today" in date_str:
        return now.date()
        
    # 2. Tomorrow
    if "tomorrow" in date_str:
        return now.date() + datetime.timedelta(days=1)
        
    # 2.5 Weekend
    if "weekend" in date_str:
        saturday_idx = 5
        days_ahead = saturday_idx - now.weekday()
        if "next" in date_str:
            if days_ahead <= 0:
                days_ahead += 7
            days_ahead += 7
        else:
            if days_ahead <= 0:
                days_ahead += 7
        return now.date() + datetime.timedelta(days=days_ahead)
        
    # 3. Next [Weekday]
    weekdays = {
        'monday': 0, 'tue': 1, 'tuesday': 1, 'wed': 2, 'wednesday': 2,
        'thu': 3, 'thursday': 3, 'fri': 4, 'friday': 4, 'sat': 5, 'saturday': 5,
        'sun': 6, 'sunday': 6
    }
    
    for day_name, day_idx in weekdays.items():
        if f"next {day_name}" in date_str or f"on {day_name}" in date_str or day_name == date_str:
            days_ahead = day_idx - now.weekday()
            if days_ahead <= 0: # Already passed or is today, go to next week
                days_ahead += 7
            return now.date() + datetime.timedelta(days=days_ahead)
            
    # 4. YYYY-MM-DD or DD-MM-YYYY format
    date_match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
    if date_match:
        try:
            return datetime.date(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
        except ValueError:
            pass
            
    date_match_reverse = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', date_str)
    if date_match_reverse:
        try:
            return datetime.date(int(date_match_reverse.group(3)), int(date_match_reverse.group(2)), int(date_match_reverse.group(1)))
        except ValueError:
            pass
            
    # Default fallback: tomorrow
    return now.date() + datetime.timedelta(days=1)

def parse_time(time_str):
    """
    Parses terms like:
    - '2:00 PM', '10:00 AM', '7:00 PM', '10 AM' (12-hour format with AM/PM)
    - '15:30', '16:00', '04:00', '4:00' (strictly 24-hour format when AM/PM is omitted)
    """
    time_str = time_str.upper().strip()
    
    # 1. Look for AM/PM in the string
    has_ampm = 'AM' in time_str or 'PM' in time_str
    
    if has_ampm:
        # Match HH:MM AM/PM
        match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            ampm = match.group(3)
            
            if ampm == 'PM' and hour < 12:
                hour += 12
            elif ampm == 'AM' and hour == 12:
                hour = 0
            try:
                return datetime.time(hour, minute)
            except ValueError:
                pass
                
        # Match HH AM/PM
        match_hour_only = re.search(r'(\d{1,2})\s*(AM|PM)', time_str)
        if match_hour_only:
            hour = int(match_hour_only.group(1))
            ampm = match_hour_only.group(2)
            
            if ampm == 'PM' and hour < 12:
                hour += 12
            elif ampm == 'AM' and hour == 12:
                hour = 0
            try:
                return datetime.time(hour, 0)
            except ValueError:
                pass
    else:
        # Strictly 24-hour format (no AM/PM)
        # Match HH:MM (24-hour)
        match_24 = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match_24:
            hour = int(match_24.group(1))
            minute = int(match_24.group(2))
            try:
                return datetime.time(hour, minute)
            except ValueError:
                pass
                
    # Default fallback: 9:00 AM
    return datetime.time(9, 0)

def extract_event_title(text):
    if not text:
        return ""
    # Extract only the first sentence or first line segment
    first_segment = re.split(r'[.\n\r;]+', text)[0].strip()
    cleaned = first_segment.lower()
    
    # 1. Remove dates and time stamps using regex
    cleaned = re.sub(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', '', cleaned)
    cleaned = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b', '', cleaned)
    cleaned = re.sub(r'\b\d{1,2}:\d{2}\s*(?:am|pm)?\b', '', cleaned)
    cleaned = re.sub(r'\b\d{1,2}\s*(?:am|pm)\b', '', cleaned)
    cleaned = re.sub(r'\b(?:at|around|@|by)\s*\d{1,2}(?::\d{2})?\b', '', cleaned)
    cleaned = re.sub(r'\bin\s+\d+\s*(?:min|minute|hour|hr)s?\b', '', cleaned)
    
    # 2. Remove relative date keywords
    to_remove = [
        "next weekend", "this weekend", "weekend", "tomorrow", "today",
        "next monday", "next tuesday", "next wednesday", "next thursday", "next friday", "next saturday", "next sunday",
        "on monday", "on tuesday", "on wednesday", "on thursday", "on friday", "on saturday", "on sunday",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ]
    
    for kw in to_remove:
        cleaned = re.sub(r'\b' + re.escape(kw) + r'\b', '', cleaned)
        
    # 3. Remove common helper prepositions and scheduling patterns
    prep_patterns = [
        r'\bremind me to\b',
        r'\bremind me of\b',
        r'\bremind me\b',
        r'\bschedule a\b',
        r'\bschedule\b',
        r'\breminder for\b',
        r'\breminder to\b',
        r'\bfor\b',
        r'\bat\b',
        r'\bon\b',
        r'\bto\b',
        r'\bin\b'
    ]
    
    for pat in prep_patterns:
        cleaned = re.sub(pat, '', cleaned)
        
    # Clean up punctuation and spacing
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip(',.?!;:-()[]{} ')
    
    if cleaned:
        return cleaned[0].upper() + cleaned[1:]
    return ""

def predict_ampm_by_context(hour, text):
    text = text.lower()
    
    # 1. Birthday / Anniversary celebrations
    if "birthday" in text or "anniversary" in text or "bday" in text:
        if hour == 12:
            return 'AM'  # 12:00 AM Midnight birthday wishes/celebration
        elif 7 <= hour <= 11:
            return 'AM'  # Morning wishes
        else:
            return 'PM'
            
    # 2. Morning activities (Gym, Workout, Wake up, Breakfast, Sunrise, Jogging, Run)
    morning_keywords = ["wake up", "wakeup", "breakfast", "gym", "workout", "jogging", "jog", "morning", "sunrise", "run", "coffee"]
    if any(kw in text for kw in morning_keywords):
        if 4 <= hour <= 11:
            return 'AM'
        elif hour == 12:
            return 'PM'  # Noon
        else:
            return 'AM'
            
    # 3. Mid-day/Lunch activities (Lunch, Noon, Brunch, Standup, Meeting, Office, Class, Work, Call, Exam, Interview)
    afternoon_keywords = ["lunch", "brunch", "noon", "afternoon", "meeting", "standup", "class", "office", "work", "call", "exam", "interview"]
    if any(kw in text for kw in afternoon_keywords):
        if hour == 12:
            return 'PM'  # Noon
        elif 1 <= hour <= 6:
            return 'PM'  # Afternoon
        elif 8 <= hour <= 11:
            return 'AM'  # Morning meetings
            
    # 4. Evening/Night activities (Dinner, Supper, Party, Sleep, Bedtime, Night, Sunset, Movie, Drinks, Club)
    evening_keywords = ["dinner", "supper", "party", "sleep", "bedtime", "night", "sunset", "movie", "drinks", "bar", "club"]
    if any(kw in text for kw in evening_keywords):
        if hour == 12:
            return 'AM'  # Midnight
        elif 1 <= hour <= 4:
            return 'AM'  # Late night
        elif 5 <= hour <= 11:
            return 'PM'  # Evening
            
    # Default fallbacks based on raw hour range if no keywords match:
    if 7 <= hour <= 11:
        return 'AM'  # Morning
    elif hour == 12 or 1 <= hour <= 6:
        return 'PM'  # Afternoon
    else:
        return 'PM'  # Night

def strip_email_quotes(text):
    if not text:
        return ""
    lines = text.splitlines()
    clean_lines = []
    for line in lines:
        line_strip = line.strip()
        # Detect standard quote or reply headers
        if (line_strip.startswith('>') or 
            line_strip.startswith('---') or 
            (line_strip.lower().startswith('on ') and 'wrote:' in line_strip.lower()) or
            'original message' in line_strip.lower() or
            ('from:' in line_strip.lower() and 'to:' in line_strip.lower())):
            break
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()

def generate_bulleted_description(title, body_text, scheduled_time=None):
    import random
    from django.utils import timezone
    from datetime import timedelta
    
    # 1. Determine timing
    if not scheduled_time:
        scheduled_time = timezone.now()
        
    hour = scheduled_time.hour
    if 5 <= hour < 12:
        timing_category = "Morning"
        timing_advices = [
            "Morning hours: Start the day focused. Ensure you get a good breakfast.",
            "Early timing: Double-check alarms to guarantee a punctual start.",
            "Morning slot: Grab a warm beverage beforehand to stay sharp."
        ]
    elif 12 <= hour < 17:
        timing_category = "Afternoon"
        timing_advices = [
            "Afternoon hours: Stay energized and check off midday priorities.",
            "Midday timing: Account for lunch breaks and peak afternoon traffic.",
            "Afternoon slot: Ideal time to stay productive and review progress."
        ]
    elif 17 <= hour < 21:
        timing_category = "Evening"
        timing_advices = [
            "Evening hours: Plan transport carefully around rush hour congestion.",
            "Evening slot: Excellent time to transition out of work and focus.",
            "Evening timing: Make sure details are finalized before twilight."
        ]
    else:
        timing_category = "Night"
        timing_advices = [
            "Late night slot: Ensure secure return transport is arranged.",
            "Night hours: Keep it brief to allow for proper rest afterwards.",
            "Late timing: Plan ahead to avoid any overnight scheduling delays."
        ]
        
    # Seed randomizer stable for this event to simulate deterministic generative AI
    seed_str = f"{title}_{scheduled_time.strftime('%Y-%m-%d_%H')}"
    random_gen = random.Random(seed_str)
    timing_advice = random_gen.choice(timing_advices)
    
    # 2. Determine weather
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["ski", "snow", "winter", "ice"]):
        weather_desc = "Freezing temperatures and snow"
        weather_advices = [
            "Forecast: Freezing temperatures. Heavy winter gear is highly recommended.",
            "Forecast: Snowy conditions. Check road/travel safety updates."
        ]
    elif any(kw in title_lower for kw in ["swim", "beach", "pool", "summer", "hot"]):
        weather_desc = "Hot and sunny skies"
        weather_advices = [
            "Forecast: High heat index. Wear sunscreen and stay hydrated.",
            "Forecast: Sunny weather. Light, breathable clothing is best."
        ]
    elif any(kw in title_lower for kw in ["rain", "storm", "wet", "shower"]):
        weather_desc = "Rain showers and wet conditions"
        weather_advices = [
            "Forecast: Rain warning. Carry an umbrella or a waterproof jacket.",
            "Forecast: Showers expected. Prepare for indoor activities."
        ]
    else:
        weather_options = [
            ("Sunny & clear skies", ["Forecast: Clear sunny weather. Ideal day for outdoor activities.", "Forecast: Sunny skies. Grab sunglasses before heading out."]),
            ("Partly cloudy & mild", ["Forecast: Partly cloudy skies. Pleasant temperature, great for transit.", "Forecast: Overcast. Comfortable weather with mild breezes."]),
            ("Light rain showers", ["Forecast: Scattered light showers. Keep a hood or umbrella handy.", "Forecast: Chances of drizzle. Plan for damp outdoor routes."]),
            ("Cool and breezy", ["Forecast: Cool breezy conditions. A light jacket or sweater is suggested.", "Forecast: Bracing wind. Dress warmly to remain comfortable."])
        ]
        chosen_weather = random_gen.choice(weather_options)
        weather_desc = chosen_weather[0]
        weather_advices = chosen_weather[1]
        
    weather_advice = random_gen.choice(weather_advices)
    
    # 3. Determine severity
    if any(kw in title_lower for kw in ["interview", "flight", "exam", "test", "presentation", "court", "deadline", "audit"]):
        severity = "Critical"
        severity_advices = [
            "Severity: CRITICAL. Arrive 30 minutes early. Double-check all credentials.",
            "Severity: CRITICAL. High importance task. Verify backup plans in advance."
        ]
    elif any(kw in title_lower for kw in ["doctor", "dentist", "medical", "meeting", "sync", "client", "dentistry", "visit"]):
        severity = "High"
        severity_advices = [
            "Severity: High. Prepare required documents and notes ahead of time.",
            "Severity: High. Minimize distractions to ensure successful completion."
        ]
    elif any(kw in title_lower for kw in ["movie", "concert", "game", "show", "cinema", "play", "relax", "coffee", "netflix"]):
        severity = "Low"
        severity_advices = [
            "Severity: Low. Casual schedule. Take it easy and enjoy the event.",
            "Severity: Low. Flexible activity. Reschedule if more pressing tasks arise."
        ]
    else:
        severity = "Normal"
        severity_advices = [
            "Severity: Normal. Standard reminder set. Proceed with routine preparation.",
            "Severity: Normal. Maintain normal checklist items to stay on track."
        ]
        
    severity_advice = random_gen.choice(severity_advices)
    
    # 4. Action details
    action_items = []
    cleaned_body = body_text.strip() if body_text else ""
    if cleaned_body:
        import re
        sentences = re.split(r'[.\n\r\t]+', cleaned_body)
        for s in sentences:
            s_clean = s.strip()
            if not s_clean or len(s_clean) > 100 or s_clean.startswith('>') or 'http' in s_clean:
                continue
            if s_clean.lower() in ['yes', 'no', 'confirm', 'cancel', 'ok']:
                continue
            s_clean = re.sub(r'\b(?:at|around|@|by)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b', '', s_clean, flags=re.IGNORECASE)
            s_clean = re.sub(r'\b(?:tomorrow|today|sunday|monday|tuesday|wednesday|thursday|friday|saturday|weekend)\b', '', s_clean, flags=re.IGNORECASE)
            s_clean = re.sub(r'\s+', ' ', s_clean).strip(',.?!;:- ')
            if len(s_clean) > 3:
                action_items.append(f"• {s_clean[0].upper() + s_clean[1:]}.")
                
    if not action_items:
        # Generate default dynamic action item based on category
        if any(kw in title_lower for kw in ["flight", "travel", "trip", "vacation", "plane"]):
            action_items.append("• Make sure to carry passport, tickets, and boarding pass.")
        elif any(kw in title_lower for kw in ["doctor", "dentist", "medical", "clinic"]):
            action_items.append("• Bring insurance cards and list of current medications.")
        elif any(kw in title_lower for kw in ["date", "dinner", "romantic"]):
            action_items.append("• Dress elegant and confirm reservations with host.")
        elif any(kw in title_lower for kw in ["meeting", "sync", "interview"]):
            action_items.append("• Review slide deck and prepare notebook/pen for notes.")
        elif any(kw in title_lower for kw in ["gym", "workout", "run"]):
            action_items.append("• Pack gym bag with water bottle and training shoes.")
        elif any(kw in title_lower for kw in ["groceries", "buy", "store"]):
            action_items.append("• Check home inventory and bring reusable bags.")
        else:
            action_items.append(f"• Prepare necessary materials for: {title}.")
            
    # Combine bullets to form 3-4 bullet description
    final_bullets = []
    # Add primary actions (up to 1 or 2)
    for act in action_items[:1]:
        final_bullets.append(act)
    # Add timing advice
    final_bullets.append(f"• {timing_advice}")
    # Add weather advice
    final_bullets.append(f"• {weather_advice}")
    # Add severity advice
    final_bullets.append(f"• {severity_advice}")
    
    return "\n".join(final_bullets[:4])

def parse_email_reminder(subject, body):
    """
    Main parsing function. Takes subject and body, and returns a dictionary with:
    - title (str)
    - description (str)
    - scheduled_time (datetime, timezone-aware)
    """
    # Strip quotes/history to prevent parsing content from previous emails
    body = strip_email_quotes(body)

    # 1. Determine title
    raw_subject = subject.strip() if subject and subject.strip() else ""
    title = re.sub(r'^(fwd|re|fw|reply|subject):\s*', '', raw_subject, flags=re.IGNORECASE).strip()
    
    is_generic = not title or title.lower() in ["reminder", "new reminder", "email reminder", "schedule", "subject", "none", "null"]
    
    # 2. Description is the body
    raw_body = body.strip() if body else ""
    
    if is_generic and raw_body:
        extracted = extract_event_title(raw_body)
        if extracted:
            title = extracted
            
    # Default title if still empty
    if not title:
        title = "Email Reminder"
        
    description = ""
    
    # 3. Date & Time Parsing
    # Combine subject and body for analysis
    combined_text = f"{subject} {body}".lower()
    
    now = timezone.now()
    
    # Check for relative time interval (e.g. "in 40 mins", "in 2 hours")
    relative_match = re.search(r'\bin\s+(\d+)\s*(min|minute|hour|hr)s?\b', combined_text)
    if relative_match:
        val = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        if unit.startswith('min'):
            target_datetime = now + datetime.timedelta(minutes=val)
        else:
            target_datetime = now + datetime.timedelta(hours=val)
            
        scheduled_time = timezone.make_aware(timezone.make_naive(target_datetime, timezone.get_current_timezone()), timezone.get_current_timezone())
        
        description = generate_bulleted_description(title, raw_body, scheduled_time)
        return {
            'title': title,
            'description': description,
            'scheduled_time': scheduled_time
        }

    # Clean text to look for dates/times
    target_date = None
    target_time = None
    
    # Try finding time first
    # A. Look for explicit time with AM/PM (e.g. 10:30 PM, 9 AM)
    time_ampm_match = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', combined_text)
    if time_ampm_match:
        hour = int(time_ampm_match.group(1))
        minute = int(time_ampm_match.group(2) or 0)
        ampm = time_ampm_match.group(3).upper()
        
        if ampm == 'PM' and hour < 12:
            hour += 12
        elif ampm == 'AM' and hour == 12:
            hour = 0
        target_time = datetime.time(hour, minute)
    else:
        # B. Look for strictly 24-hour style format (e.g. 15:30, 04:00)
        time_24_match = re.search(r'\b(\d{2}):(\d{2})\b', combined_text)
        if time_24_match:
            hour = int(time_24_match.group(1))
            minute = int(time_24_match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                target_time = datetime.time(hour, minute)
        
        # C. Look for ambiguous hours/times with keyword context (e.g. "at 12", "at 8")
        if not target_time:
            ambiguous_match = re.search(r'\b(?:at|around|@|by)\s*(\d{1,2})(?::(\d{2}))?\b', combined_text)
            if ambiguous_match:
                hour = int(ambiguous_match.group(1))
                minute = int(ambiguous_match.group(2) or 0)
                if 1 <= hour <= 12:
                    ampm = predict_ampm_by_context(hour, combined_text)
                    if ampm == 'PM' and hour < 12:
                        hour += 12
                    elif ampm == 'AM' and hour == 12:
                        hour = 0
                    target_time = datetime.time(hour, minute)
                elif 13 <= hour <= 23:
                    target_time = datetime.time(hour, minute)
    
    # Try relative date indicators
    date_keywords = [
        "next weekend", "this weekend", "weekend", "tomorrow", "today",
        "next monday", "next tuesday", "next wednesday", "next thursday", "next friday", "next saturday", "next sunday",
        "on monday", "on tuesday", "on wednesday", "on thursday", "on friday", "on saturday", "on sunday",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ]
    found_keyword = None
    for kw in date_keywords:
        if kw in combined_text:
            found_keyword = kw
            break
            
    if found_keyword:
        target_date = parse_relative_date(found_keyword, now)
    else:
        # Check for numeric date pattern in combined text
        date_pattern_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})', combined_text)
        if date_pattern_match:
            target_date = parse_relative_date(date_pattern_match.group(0), now)
            
    # Default fallbacks
    if not target_date:
        target_date = now.date() + datetime.timedelta(days=1) # Default tomorrow
    if not target_time:
        target_time = datetime.time(9, 0) # Default 9 AM
        
    scheduled_datetime = datetime.datetime.combine(target_date, target_time)
    
    # Make timezone aware
    scheduled_time = timezone.make_aware(scheduled_datetime, timezone.get_current_timezone())
    
    description = generate_bulleted_description(title, raw_body, scheduled_time)
    return {
        'title': title,
        'description': description,
        'scheduled_time': scheduled_time
    }
