"""Application settings and configuration."""

import os
from typing import Dict, List

import pytz


def get_timezone() -> pytz.BaseTzInfo:
    """Get the configured timezone.
    
    Returns:
        pytz.BaseTzInfo: The configured timezone.
    """
    tz_name = os.getenv("TIMEZONE", "America/New_York")
    return pytz.timezone(tz_name)


def get_weekly_schedule() -> Dict[int, List[str]]:
    """Get the weekly posting schedule.
    
    Returns:
        Dict[int, List[str]]: A dictionary mapping weekday numbers (0-6, where 0 is Monday)
                             to a list of times in 'HH:MM' format.
    """
    # Default schedule (Monday 7 AM, Wednesday 11 AM, Friday 5 PM, Saturday 9 AM, Sunday 6 PM)
    default_schedule = {
        0: ["07:00"],  # Monday
        2: ["11:00"],  # Wednesday
        4: ["17:00"],  # Friday
        5: ["09:00"],  # Saturday
        6: ["18:00"]   # Sunday
    }
    
    schedule_str = os.getenv("WEEKLY_SCHEDULE")
    if not schedule_str:
        return default_schedule
    
    # Parse schedule from environment variable
    # Format: "0:07:00,2:11:00,4:17:00,5:09:00,6:18:00"
    schedule = {}
    for entry in schedule_str.split(','):
        try:
            day_str, time_str = entry.split(':', 1)
            day = int(day_str)
            if day not in schedule:
                schedule[day] = []
            schedule[day].append(time_str)
        except (ValueError, IndexError):
            continue
    
    return schedule or default_schedule


# Timezone and schedule configuration
TIMEZONE = get_timezone()
WEEKLY_SCHEDULE = get_weekly_schedule()
