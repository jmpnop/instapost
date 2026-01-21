"""Schedule rebalancing utilities."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Set
import logging

from instapost.utils import load_json, save_json, PROJECT_ROOT
from instapost.settings import TIMEZONE, WEEKLY_SCHEDULE

logger = logging.getLogger(__name__)

SCHEDULE_FILE = PROJECT_ROOT / "schedule.json"


def get_expected_slots(start_date: datetime, days: int = 365) -> List[datetime]:
    """Generate expected time slots based on weekly schedule.

    Args:
        start_date: Starting date for slot generation (only future slots from this time)
        days: Number of days to look ahead

    Returns:
        List of expected datetime slots in the future
    """
    slots = []
    now = datetime.now(TIMEZONE)

    for i in range(days):
        check_date = start_date + timedelta(days=i)
        weekday = check_date.weekday()

        if weekday in WEEKLY_SCHEDULE:
            for time_str in WEEKLY_SCHEDULE[weekday]:
                try:
                    time_parts = time_str.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    slot = TIMEZONE.localize(
                        datetime(check_date.year, check_date.month, check_date.day, hour, minute, second)
                    )
                    # Only include future slots
                    if slot > now:
                        slots.append(slot)
                except (ValueError, TypeError, IndexError):
                    logger.warning(f"Invalid time format in schedule: {time_str}")
                    continue

    return sorted(slots)


def find_gaps(scheduled_posts: List[Dict], start_date: datetime, days: int = 365) -> List[datetime]:
    """Find gaps in the schedule (expected slots with no posts).

    Args:
        scheduled_posts: List of scheduled post entries
        start_date: Starting date for gap detection
        days: Number of days to check

    Returns:
        List of datetime slots that are empty
    """
    # Get all expected slots
    expected_slots = get_expected_slots(start_date, days)

    # Get all currently scheduled times
    scheduled_times = set()
    for post in scheduled_posts:
        try:
            post_time = datetime.fromisoformat(post['time']).replace(tzinfo=TIMEZONE)
            scheduled_times.add(post_time)
        except (ValueError, KeyError, TypeError):
            logger.warning(f"Invalid time in post: {post.get('time')}")
            continue

    # Find gaps
    gaps = [slot for slot in expected_slots if slot not in scheduled_times]

    return gaps


def rebalance_schedule(dry_run: bool = True) -> Dict:
    """Rebalance schedule by filling gaps with posts from the end.

    Args:
        dry_run: If True, only show what would be done without making changes

    Returns:
        Dictionary with rebalancing results
    """
    # Load current schedule
    schedule = load_json(SCHEDULE_FILE)

    if not isinstance(schedule, list) or not schedule:
        return {
            'success': False,
            'error': 'Schedule is empty or invalid',
            'gaps_found': 0,
            'posts_moved': 0
        }

    # Load processed posts to exclude them from rebalancing
    processed = load_json(PROJECT_ROOT / "processed.json")
    processed_filenames = {p['filename'] for p in processed} if processed else set()

    # Filter out already processed posts from schedule
    schedule = [post for post in schedule if post.get('filename') not in processed_filenames]

    # Find gaps starting from today
    now = datetime.now(TIMEZONE)
    gaps = find_gaps(schedule, now)

    if not gaps:
        return {
            'success': True,
            'message': 'No gaps found in schedule',
            'gaps_found': 0,
            'posts_moved': 0
        }

    # Filter gaps to only future ones
    future_gaps = [gap for gap in gaps if gap > now]

    if not future_gaps:
        return {
            'success': True,
            'message': 'No future gaps to fill',
            'gaps_found': len(gaps),
            'posts_moved': 0
        }

    # Sort schedule by time
    schedule_sorted = sorted(schedule, key=lambda x: datetime.fromisoformat(x['time']))

    # Find how many posts we can move (from the end)
    num_to_move = min(len(future_gaps), len(schedule_sorted))

    # Get posts from the end
    posts_to_move = schedule_sorted[-num_to_move:]
    remaining_posts = schedule_sorted[:-num_to_move]

    # Sort future gaps chronologically
    future_gaps_sorted = sorted(future_gaps)

    # Create new entries with gap times
    moved_posts = []
    for post, new_time in zip(posts_to_move, future_gaps_sorted[:num_to_move]):
        new_entry = post.copy()
        new_entry['time'] = new_time.isoformat()
        moved_posts.append(new_entry)

    # Combine remaining and moved posts
    new_schedule = remaining_posts + moved_posts
    new_schedule_sorted = sorted(new_schedule, key=lambda x: datetime.fromisoformat(x['time']))

    result = {
        'success': True,
        'gaps_found': len(future_gaps),
        'posts_moved': num_to_move,
        'dry_run': dry_run,
        'changes': []
    }

    # Record changes
    for old_post, new_post in zip(posts_to_move, moved_posts):
        old_time = datetime.fromisoformat(old_post['time'])
        new_time = datetime.fromisoformat(new_post['time'])
        result['changes'].append({
            'filename': old_post['filename'],
            'old_time': old_time.strftime('%Y-%m-%d %H:%M'),
            'new_time': new_time.strftime('%Y-%m-%d %H:%M')
        })

    # Apply changes if not dry run
    if not dry_run:
        save_json(SCHEDULE_FILE, new_schedule_sorted)
        result['message'] = f'Successfully moved {num_to_move} posts to fill gaps'
    else:
        result['message'] = f'Would move {num_to_move} posts to fill {len(future_gaps)} gaps'

    return result


if __name__ == '__main__':
    # For testing
    import sys
    from instapost.utils import setup_logging

    setup_logging('rebalance')

    dry_run = '--apply' not in sys.argv
    result = rebalance_schedule(dry_run=dry_run)

    print(f"\nRebalance Results:")
    print(f"==================")
    print(f"Gaps found: {result['gaps_found']}")
    print(f"Posts to move: {result['posts_moved']}")
    print(f"Mode: {'DRY RUN' if result.get('dry_run') else 'APPLIED'}")
    print(f"\n{result.get('message', '')}")

    if result.get('changes'):
        print(f"\nChanges:")
        for change in result['changes'][:10]:
            print(f"  {change['filename']}")
            print(f"    {change['old_time']} → {change['new_time']}")
        if len(result['changes']) > 10:
            print(f"  ... and {len(result['changes']) - 10} more")
