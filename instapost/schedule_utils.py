"""Schedule validation and management utilities."""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pytz

from instapost.utils import load_json, save_json
from instapost.settings import TIMEZONE


class ScheduleValidationError(Exception):
    """Raised when schedule validation fails."""
    pass


def validate_schedule_time(scheduled_time: str) -> Tuple[bool, Optional[str]]:
    """Validate a scheduled time.

    Args:
        scheduled_time: ISO format time string

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        dt = datetime.fromisoformat(scheduled_time)

        # Add timezone if not present
        if dt.tzinfo is None:
            dt = TIMEZONE.localize(dt)

        # Check if time is in the past
        now = datetime.now(TIMEZONE)
        if dt < now:
            minutes_ago = (now - dt).total_seconds() / 60
            return False, f"Time is in the past ({minutes_ago:.0f} minutes ago)"

        return True, None

    except ValueError as e:
        return False, f"Invalid time format: {e}"


def check_time_conflicts(schedule: List[Dict], new_time: str, exclude_filename: Optional[str] = None) -> List[str]:
    """Check for scheduling conflicts (multiple posts at same time).

    Args:
        schedule: Current schedule list
        new_time: New time to check
        exclude_filename: Filename to exclude from conflict check (for rescheduling)

    Returns:
        List of conflicting filenames
    """
    conflicts = []

    try:
        new_dt = datetime.fromisoformat(new_time)
        if new_dt.tzinfo is None:
            new_dt = TIMEZONE.localize(new_dt)

        for entry in schedule:
            if exclude_filename and entry.get('filename') == exclude_filename:
                continue

            entry_dt = datetime.fromisoformat(entry['time'])
            if entry_dt.tzinfo is None:
                entry_dt = TIMEZONE.localize(entry_dt)

            # Check if times are within 1 minute of each other
            time_diff = abs((new_dt - entry_dt).total_seconds())
            if time_diff < 60:  # Within 1 minute
                conflicts.append(entry['filename'])

    except Exception:
        pass

    return conflicts


def add_to_schedule(filename: str, scheduled_time: str, original_path: str, caption: Optional[str] = None) -> None:
    """Add an entry to the schedule with validation.

    Args:
        filename: Image filename
        scheduled_time: ISO format time
        original_path: Original file path
        caption: Optional caption for the post

    Raises:
        ScheduleValidationError: If validation fails
    """
    # Validate time
    is_valid, error = validate_schedule_time(scheduled_time)
    if not is_valid:
        raise ScheduleValidationError(f"Invalid schedule time: {error}")

    # Load current schedule
    schedule = load_json("schedule.json")

    # Check for conflicts
    conflicts = check_time_conflicts(schedule, scheduled_time)
    if conflicts:
        raise ScheduleValidationError(
            f"Time conflict with existing post(s): {', '.join(conflicts)}"
        )

    # Add entry
    entry = {
        'filename': filename,
        'time': scheduled_time,
        'original_path': original_path
    }

    if caption:
        entry['caption'] = caption

    schedule.append(entry)

    # Save schedule
    save_json("schedule.json", schedule)


def update_schedule_entry(filename: str, new_time: Optional[str] = None, new_caption: Optional[str] = None) -> None:
    """Update an existing schedule entry.

    Args:
        filename: Image filename to update
        new_time: New scheduled time (optional)
        new_caption: New caption (optional)

    Raises:
        ScheduleValidationError: If validation fails or entry not found
    """
    schedule = load_json("schedule.json")

    # Find entry
    entry = None
    for e in schedule:
        if e.get('filename') == filename:
            entry = e
            break

    if not entry:
        raise ScheduleValidationError(f"Entry not found: {filename}")

    # Update time if provided
    if new_time:
        is_valid, error = validate_schedule_time(new_time)
        if not is_valid:
            raise ScheduleValidationError(f"Invalid schedule time: {error}")

        conflicts = check_time_conflicts(schedule, new_time, exclude_filename=filename)
        if conflicts:
            raise ScheduleValidationError(
                f"Time conflict with existing post(s): {', '.join(conflicts)}"
            )

        entry['time'] = new_time

    # Update caption if provided
    if new_caption is not None:
        if new_caption:
            entry['caption'] = new_caption
        elif 'caption' in entry:
            del entry['caption']

    # Save schedule
    save_json("schedule.json", schedule)


def remove_from_schedule(filename: str) -> None:
    """Remove an entry from the schedule.

    Args:
        filename: Image filename to remove

    Raises:
        ScheduleValidationError: If entry not found
    """
    schedule = load_json("schedule.json")
    original_count = len(schedule)

    schedule = [e for e in schedule if e.get('filename') != filename]

    if len(schedule) == original_count:
        raise ScheduleValidationError(f"Entry not found: {filename}")

    save_json("schedule.json", schedule)
