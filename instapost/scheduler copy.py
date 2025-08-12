import os
import json
import time
from datetime import datetime, timedelta
import pytz
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Timezone and schedule configuration
TIMEZONE = "America/New_York"
WEEKLY_SCHEDULE = {
    0: ["07:00"],  # Monday
    2: ["11:00"],  # Wednesday
    4: ["17:00"],  # Friday
    5: ["09:00"],  # Saturday
    6: ["18:00"]  # Sunday
}

SCHEDULE_FILE = "schedule.json"
IMAGES_DIR = "images"


def load_schedule():
    """Load the schedule from JSON file or initialize if not exists."""
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r') as f:
            return json.load(f)
    return []


def save_schedule(schedule):
    """Save the schedule to JSON file."""
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule, f, indent=4)


def get_next_scheduled_time():
    """Calculate the next available scheduled time based on the weekly schedule."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Check for the next slot starting from today
    for offset in range(7):
        candidate_day = now + timedelta(days=offset)
        weekday = candidate_day.weekday()
        if weekday in WEEKLY_SCHEDULE:
            for time_str in WEEKLY_SCHEDULE[weekday]:
                scheduled_time = tz.localize(datetime.strptime(f"{candidate_day.date()} {time_str}", "%Y-%m-%d %H:%M"))
                if scheduled_time > now:
                    return scheduled_time.isoformat()

    # If no slot found (unlikely), fallback to next Monday
    next_monday = now + timedelta(days=(7 - now.weekday()) % 7)
    return tz.localize(datetime.strptime(f"{next_monday.date()} 07:00", "%Y-%m-%d %H:%M")).isoformat()


class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(('.png', '.jpg', '.jpeg')):
            filepath = event.src_path
            print(f"New image detected: {filepath}")

            # Load current schedule
            schedule = load_schedule()

            # Add new entry
            new_entry = {
                "filepath": filepath,
                "scheduled_time": get_next_scheduled_time(),
                "status": "pending",
                "posted_time": None,
                "instagram_url": None
            }
            schedule.append(new_entry)

            # Save updated schedule
            save_schedule(schedule)
            print(f"Added to schedule: {new_entry}")


if __name__ == "__main__":
    # Ensure images directory exists
    os.makedirs(IMAGES_DIR, exist_ok=True)

    event_handler = ImageHandler()
    observer = Observer()
    observer.schedule(event_handler, path=IMAGES_DIR, recursive=False)
    observer.start()

    print(f"Monitoring {IMAGES_DIR} for new images...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()