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
    Parses terms like '2:00 PM', '10:00 AM', '7:00 PM', '10 AM', '15:30' and returns a time object.
    """
    time_str = time_str.upper().strip()
    
    # Match HH:MM AM/PM
    match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)?', time_str)
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
            
    # Match 24 hour HH:MM
    match_24 = re.search(r'(\d{2}):(\d{2})', time_str)
    if match_24:
        hour = int(match_24.group(1))
        minute = int(match_24.group(2))
        try:
            return datetime.time(hour, minute)
        except ValueError:
            pass
            
    # Default fallback: 9:00 AM
    return datetime.time(9, 0)

def parse_email_reminder(subject, body):
    """
    Main parsing function. Takes subject and body, and returns a dictionary with:
    - title (str)
    - description (str)
    - scheduled_time (datetime, timezone-aware)
    """
    # 1. Determine title
    title = subject.strip() if subject and subject.strip() else "Email Reminder"
    
    # Remove prefix like Fwd:, Re:, etc.
    title = re.sub(r'^(fwd|re|fw|reply|subject):\s*', '', title, flags=re.IGNORECASE).strip()
    
    # 2. Description is the body
    description = body.strip() if body else ""
    
    # 3. Date & Time Parsing
    # Combine subject and body for analysis
    combined_text = f"{subject} {body}".lower()
    
    now = timezone.now()
    
    # Clean text to look for dates/times
    target_date = None
    target_time = None
    
    # Try finding time first
    time_matches = re.findall(r'(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))', combined_text)
    if time_matches:
        target_time = parse_time(time_matches[0])
    
    # Try relative date indicators
    date_keywords = ["tomorrow", "today", "next monday", "next tuesday", "next wednesday", "next thursday", "next friday", "next saturday", "next sunday"]
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
    
    return {
        'title': title,
        'description': description,
        'scheduled_time': scheduled_time
    }
