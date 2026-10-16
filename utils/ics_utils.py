# utils/ics_utils.py
from datetime import datetime, timedelta
import re

def generate_task_ics(title: str, date_str: str | None = None, time_str: str | None = None) -> str:
    """
    Generates an RFC 5545 iCalendar string using floating local time.
    """
    now = datetime.now()
    
    # 1. Parse date or default to today
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = now.date()
    else:
        target_date = now.date()

    # 2. Parse time (e.g., "10:00", "2:30pm", "10:30 - 11:00")
    start_time = datetime.min.time().replace(hour=9, minute=0)  # Fallback default 9:00 AM
    if time_str:
        time_match = re.search(r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b', time_str, re.IGNORECASE)
        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            ampm = time_match.group(3).lower() if time_match.group(3) else None

            if ampm == 'pm' and hours < 12:
                hours += 12
            elif ampm == 'am' and hours == 12:
                hours = 0

            start_time = datetime.min.time().replace(hour=hours, minute=minutes)

    start_dt = datetime.combine(target_date, start_time)
    end_dt = start_dt + timedelta(hours=1)

    # Floating local time format: YYYYMMDDTHHMMSS (No 'Z' suffix)
    def fmt_local(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%S")

    # Clean title for iCalendar format
    clean_title = title.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Executive Focus Engine//Task Calendar Export//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:task-{int(now.timestamp())}@focus-engine",
        f"DTSTAMP:{fmt_local(now)}",
        f"DTSTART:{fmt_local(start_dt)}",
        f"DTEND:{fmt_local(end_dt)}",
        f"SUMMARY:{clean_title}",
        "DESCRIPTION:Generated from Executive Focus Engine",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR"
    ]

    return "\r\n".join(ics_lines)