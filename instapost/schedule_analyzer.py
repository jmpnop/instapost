"""Analyze schedule data to provide accurate status reports.

This module ensures accurate analysis by:
1. Reading actual WEEKLY_SCHEDULE from environment
2. Calculating valid posting slots from calendar dates
3. Cross-referencing with schedule.json and processed.json
4. Preventing manual calculation errors
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from instapost.utils import load_json, PROJECT_ROOT
from instapost.settings import TIMEZONE, WEEKLY_SCHEDULE


SCHEDULE_FILE = PROJECT_ROOT / "schedule.json"
PROCESSED_FILE = PROJECT_ROOT / "processed.json"


def get_valid_posting_slots(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Get all valid posting slots between two dates based on WEEKLY_SCHEDULE.

    Args:
        start_date: Start of date range (timezone-aware)
        end_date: End of date range (timezone-aware)

    Returns:
        List of datetime objects for valid posting slots
    """
    slots = []

    # Iterate through each day in range
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=23, minute=59, second=59, microsecond=0)

    while current <= end:
        weekday = current.weekday()

        # Check if this weekday has any scheduled times
        if weekday in WEEKLY_SCHEDULE:
            for time_str in WEEKLY_SCHEDULE[weekday]:
                try:
                    # Parse time string (format: "HH:MM:SS" or "HH:MM")
                    time_parts = time_str.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0

                    # Create slot datetime
                    slot_time = current.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # Only include if within range
                    if start_date <= slot_time <= end_date:
                        slots.append(slot_time)
                except (ValueError, IndexError) as e:
                    print(f"Warning: Invalid time format '{time_str}': {e}")
                    continue

        current += timedelta(days=1)

    return sorted(slots)


def get_scheduled_posts() -> Dict[str, dict]:
    """
    Load schedule.json and return as dict keyed by filename.

    Returns:
        Dict mapping filename to schedule entry
    """
    try:
        schedule = load_json(SCHEDULE_FILE)
        return {entry['filename']: entry for entry in schedule}
    except Exception as e:
        print(f"Error loading schedule.json: {e}")
        return {}


def get_processed_posts() -> Dict[str, dict]:
    """
    Load processed.json and return as dict keyed by filename.

    Returns:
        Dict mapping filename to processed entry
    """
    try:
        processed = load_json(PROCESSED_FILE)
        return {entry['filename']: entry for entry in processed}
    except Exception as e:
        print(f"Error loading processed.json: {e}")
        return {}


def analyze_outage_period(
    crash_time: datetime,
    restart_time: datetime
) -> Dict[str, any]:
    """
    Analyze what happened during a daemon outage period.

    Args:
        crash_time: When daemons crashed (timezone-aware)
        restart_time: When daemons restarted (timezone-aware)

    Returns:
        Dictionary containing:
        - valid_slots: List of valid posting slots during outage
        - scheduled_posts: Posts that were scheduled for those slots
        - missed_posts: Posts scheduled but not posted
        - delayed_posts: Posts posted late after restart
    """
    # Get all valid posting slots during outage
    valid_slots = get_valid_posting_slots(crash_time, restart_time)

    # Load schedule and processed data
    scheduled = get_scheduled_posts()
    processed = get_processed_posts()

    # Analyze each valid slot
    slot_analysis = []
    missed_posts = []
    delayed_posts = []

    for slot in valid_slots:
        # Find if any post was scheduled for this slot
        scheduled_for_slot = None

        for filename, entry in scheduled.items():
            try:
                scheduled_time = datetime.fromisoformat(entry['time'])
                if scheduled_time.tzinfo is None:
                    scheduled_time = TIMEZONE.localize(scheduled_time)

                # Check if scheduled for this slot (within 1 minute)
                if abs((scheduled_time - slot).total_seconds()) < 60:
                    scheduled_for_slot = {
                        'filename': filename,
                        'scheduled_time': scheduled_time,
                        'entry': entry
                    }
                    break
            except (ValueError, KeyError) as e:
                print(f"Warning: Invalid schedule entry for {filename}: {e}")
                continue

        slot_info = {
            'slot_time': slot,
            'had_post': scheduled_for_slot is not None,
            'post': scheduled_for_slot
        }

        # Check if the post was processed
        if scheduled_for_slot:
            filename = scheduled_for_slot['filename']

            if filename in processed:
                posted_time = datetime.fromisoformat(processed[filename]['timestamp'])
                if posted_time.tzinfo is None:
                    posted_time = TIMEZONE.localize(posted_time)

                delay_hours = (posted_time - scheduled_for_slot['scheduled_time']).total_seconds() / 3600

                slot_info['posted'] = True
                slot_info['posted_time'] = posted_time
                slot_info['delay_hours'] = delay_hours

                if delay_hours > 1:
                    delayed_posts.append({
                        'filename': filename,
                        'scheduled': scheduled_for_slot['scheduled_time'],
                        'posted': posted_time,
                        'delay_hours': delay_hours,
                        'url': processed[filename].get('url')
                    })
            else:
                slot_info['posted'] = False
                missed_posts.append({
                    'filename': filename,
                    'scheduled': scheduled_for_slot['scheduled_time'],
                    'slot': slot
                })

        slot_analysis.append(slot_info)

    return {
        'valid_slots': valid_slots,
        'slot_analysis': slot_analysis,
        'missed_posts': missed_posts,
        'delayed_posts': delayed_posts,
        'total_slots': len(valid_slots),
        'slots_with_posts': sum(1 for s in slot_analysis if s['had_post']),
        'slots_without_posts': sum(1 for s in slot_analysis if not s['had_post']),
        'posts_missed': len(missed_posts),
        'posts_delayed': len(delayed_posts)
    }


def format_outage_report(crash_time: datetime, restart_time: datetime) -> str:
    """
    Generate a formatted report of outage impact.

    Args:
        crash_time: When daemons crashed
        restart_time: When daemons restarted

    Returns:
        Formatted string report
    """
    analysis = analyze_outage_period(crash_time, restart_time)

    lines = []
    lines.append("OUTAGE IMPACT ANALYSIS")
    lines.append("=" * 70)
    lines.append(f"Crash:   {crash_time.strftime('%a %b %d, %Y at %H:%M %Z')}")
    lines.append(f"Restart: {restart_time.strftime('%a %b %d, %Y at %H:%M %Z')}")
    lines.append(f"Duration: {(restart_time - crash_time).total_seconds() / 3600:.1f} hours")
    lines.append("")

    lines.append("POSTING SLOTS DURING OUTAGE:")
    lines.append(f"  Total valid slots: {analysis['total_slots']}")
    lines.append(f"  Slots with posts scheduled: {analysis['slots_with_posts']}")
    lines.append(f"  Empty slots (no post scheduled): {analysis['slots_without_posts']}")
    lines.append("")

    if analysis['slot_analysis']:
        lines.append("SLOT DETAILS:")
        for slot_info in analysis['slot_analysis']:
            slot_time = slot_info['slot_time']
            lines.append(f"\n  {slot_time.strftime('%a %b %d, %H:%M')}:")

            if slot_info['had_post']:
                post = slot_info['post']
                lines.append(f"    Image: {post['filename'][:50]}...")

                if slot_info.get('posted'):
                    posted_time = slot_info['posted_time']
                    delay = slot_info['delay_hours']
                    lines.append(f"    Posted: {posted_time.strftime('%a %b %d, %H:%M')} ({delay:.1f}h late)")
                else:
                    lines.append(f"    Status: ❌ NEVER POSTED")
            else:
                lines.append(f"    Status: Empty slot (no post scheduled)")

    lines.append("")
    lines.append("SUMMARY:")
    lines.append(f"  Posts missed completely: {analysis['posts_missed']}")
    lines.append(f"  Posts delayed: {analysis['posts_delayed']}")

    if analysis['delayed_posts']:
        lines.append("")
        lines.append("DELAYED POSTS:")
        for post in analysis['delayed_posts']:
            lines.append(f"  - {post['filename'][:50]}...")
            lines.append(f"    Scheduled: {post['scheduled'].strftime('%a %b %d, %H:%M')}")
            lines.append(f"    Posted: {post['posted'].strftime('%a %b %d, %H:%M')}")
            lines.append(f"    Delay: {post['delay_hours']:.1f} hours")
            if post.get('url'):
                lines.append(f"    URL: {post['url']}")

    return '\n'.join(lines)


if __name__ == '__main__':
    # Example usage: analyze the recent outage
    import pytz

    tz = pytz.timezone('America/New_York')
    crash = tz.localize(datetime(2026, 2, 9, 13, 0))
    restart = tz.localize(datetime(2026, 2, 13, 1, 0))

    print(format_outage_report(crash, restart))
