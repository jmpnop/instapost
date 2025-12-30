import sys
import os
import time
import shutil
import json
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
from PIL import Image, UnidentifiedImageError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from instapost.utils import load_json, save_json, PROJECT_ROOT, setup_logging, ensure_single_instance, show_idle_animation
from instapost.settings import TIMEZONE, WEEKLY_SCHEDULE
from instapost.daemons.scheduler import get_next_scheduled_time
from instapost.validation import validate_image_file, get_image_info
from instapost.schedule_utils import add_to_schedule, ScheduleValidationError

logger = setup_logging('watcher')

# Instagram only supports these formats
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png']
SCHEDULE_FILE = "schedule.json"

class ScheduleIterator:
    """Iterator that provides the next available time slot for scheduling."""
    
    def __init__(self):
        # Parse the weekly schedule into a dict of {weekday: [times]}
        self.weekly_schedule = {
            0: [],  # Monday
            1: [],  # Tuesday
            2: [],  # Wednesday
            3: [],  # Thursday
            4: [],  # Friday
            5: [],  # Saturday
            6: [],  # Sunday
        }
        
        # Process the WEEKLY_SCHEDULE from settings
        if isinstance(WEEKLY_SCHEDULE, dict):
            # Already in the correct format
            for day, times in WEEKLY_SCHEDULE.items():
                if isinstance(times, list):
                    self.weekly_schedule[int(day)] = sorted(times)
        else:
            # Try to parse as string (for backward compatibility)
            try:
                for entry in str(WEEKLY_SCHEDULE).split(','):
                    try:
                        day_str, time_str = entry.split(':', 1)
                        day = int(day_str)
                        if 0 <= day <= 6:
                            self.weekly_schedule[day].append(time_str)
                    except (ValueError, IndexError):
                        continue
            except (AttributeError, TypeError):
                pass

        # Sort times for each day
        for day in self.weekly_schedule:
            self.weekly_schedule[day].sort()

    def _get_last_scheduled_time(self):
        """Get the last scheduled time from schedule.json"""
        schedule = load_json(SCHEDULE_FILE)
        if not isinstance(schedule, list) or not schedule:
            return None
            
        try:
            # Get the most recent scheduled time
            last_time = max(
                datetime.fromisoformat(entry['time']).replace(tzinfo=TIMEZONE)
                for entry in schedule
                if 'time' in entry
            )
            return last_time
        except (ValueError, KeyError):
            return None

    def next_slot(self) -> str:
        """Get the next available time slot based on the current schedule."""
        now = datetime.now(TIMEZONE)
        last_time = self._get_last_scheduled_time()
        
        # If this is the first scheduling, start from now
        if not last_time:
            # Find the next available slot from now
            current_date = now.date()
            for _ in range(14):  # Check next 14 days
                weekday = current_date.weekday()
                if weekday in self.weekly_schedule and self.weekly_schedule[weekday]:  # Check if day has slots
                    for time_str in self.weekly_schedule[weekday]:
                        slot_time = TIMEZONE.localize(
                            datetime.combine(
                                current_date,
                                dt_time(*map(int, time_str.split(':')))
                            )
                        )
                        if slot_time > now:
                            return slot_time.isoformat()
                current_date += timedelta(days=1)
            raise ValueError("No available time slots found in the next 14 days")
        
        # If we have a last scheduled time, find the next slot after it
        last_date = last_time.date()
        last_weekday = last_time.weekday()
        last_time_str = last_time.strftime('%H:%M')
        
        # Check if there are more slots on the same day
        if last_weekday in self.weekly_schedule and self.weekly_schedule[last_weekday]:  # Check if day has slots
            day_slots = self.weekly_schedule[last_weekday]
            try:
                next_slot_idx = day_slots.index(last_time_str) + 1
                if next_slot_idx < len(day_slots):
                    next_time = TIMEZONE.localize(
                        datetime.combine(
                            last_date,
                            dt_time(*map(int, day_slots[next_slot_idx].split(':')))
                        )
                    )
                    if next_time > now:
                        return next_time.isoformat()
            except ValueError:
                pass
        
        # If no more slots today, find the next day with slots
        current_date = last_date + timedelta(days=1)
        for _ in range(14):  # Check next 14 days
            weekday = current_date.weekday()
            if weekday in self.weekly_schedule and self.weekly_schedule[weekday]:  # Check if day has slots
                next_time = TIMEZONE.localize(
                    datetime.combine(
                        current_date,
                        dt_time(*map(int, self.weekly_schedule[weekday][0].split(':')))
                    )
                )
                if next_time > now:
                    return next_time.isoformat()
            current_date += timedelta(days=1)
        
        raise ValueError("No available time slots found in the next 14 days")

class ImageHandler(FileSystemEventHandler):
    """Handle file system events for image files."""
    
    def __init__(self, schedule_iterator):
        super().__init__()
        self.schedule_iterator = schedule_iterator

    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory and any(event.src_path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            self._process_file(event.src_path)

    def on_moved(self, event):
        """Called when a file or directory is moved/renamed."""
        if not event.is_directory and any(event.dest_path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            self._process_file(event.dest_path)

    def on_modified(self, event):
        """Called when a file or directory is modified."""
        if not event.is_directory and any(event.src_path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            self._process_file(event.src_path)

    def _process_file(self, file_path, scheduled_time=None):
        """Process a new or renamed file."""
        try:
            if not self._is_image(file_path):
                logger.warning(f"Skipping non-image file: {file_path}")
                return
                
            if self._is_already_processed(file_path):
                logger.info(f"Skipping already processed file: {file_path}")
                return
                
            if self._is_already_scheduled(file_path):
                logger.info(f"Skipping already scheduled file: {file_path}")
                return
                
            # Get the next available time slot
            scheduled_time = self.schedule_iterator.next_slot()
            self._schedule_image(file_path, scheduled_time)
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    def _is_image(self, file_path):
        """Check if the file is a valid image for Instagram."""
        is_valid, error = validate_image_file(file_path)
        if not is_valid:
            logger.warning(f"Image validation failed for {file_path}: {error}")
            # Log detailed info for debugging
            info = get_image_info(file_path)
            logger.debug(f"Image info: {info['width']}x{info['height']}, "
                        f"{info['size_mb']:.2f}MB, "
                        f"aspect ratio: {info['aspect_ratio']:.2f}")
        return is_valid

    def _is_already_processed(self, file_path):
        """Check if the image has already been processed."""
        processed = load_json("processed.json")
        filename = os.path.basename(file_path)
        return any(entry.get('filename') == filename for entry in processed)
        
    def _is_already_scheduled(self, file_path):
        """Check if the image is already in the schedule."""
        schedule = load_json(SCHEDULE_FILE)
        if not isinstance(schedule, list):
            return False
        filename = os.path.basename(file_path)
        return any(entry.get('filename') == filename for entry in schedule)

    def _schedule_image(self, image_path, scheduled_time):
        """Schedule an image for posting with validation."""
        try:
            # Check for optional .txt file with caption
            caption = None
            txt_file = Path(image_path).with_suffix('.txt')
            if txt_file.exists():
                try:
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        caption = f.read().strip()
                        if caption:
                            logger.info(f"Found caption in .txt file: {caption[:50]}..." if len(caption) > 50 else caption)
                except Exception as e:
                    logger.warning(f"Failed to read .txt file for {image_path}: {e}")

            # Add to schedule with validation
            add_to_schedule(
                filename=os.path.basename(image_path),
                scheduled_time=scheduled_time,
                original_path=image_path,
                caption=caption
            )

            scheduled_time_str = datetime.fromisoformat(scheduled_time).strftime("%Y-%m-%d %H:%M")
            caption_info = f" with caption" if caption else ""
            logger.info(f"Scheduled {os.path.basename(image_path)} for {scheduled_time_str}{caption_info}")

        except ScheduleValidationError as e:
            logger.error(f"Schedule validation failed for {image_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to schedule {image_path}: {e}")

def watch_directory(watch_dir):
    """Start watching a directory for new images."""
    ensure_single_instance('watcher')
    
    watch_path = Path(watch_dir).resolve()
    if not watch_path.exists() or not watch_path.is_dir():
        logger.error(f"Error: {watch_path} is not a valid directory")
        return False

    # Initialize the schedule iterator
    schedule_iterator = ScheduleIterator()
    event_handler = ImageHandler(schedule_iterator)
    
    # Process existing files in the directory
    logger.info(f"Processing existing files in {watch_path}")
    
    # Process each file
    for file_path in sorted(watch_path.glob('*')):
        if (file_path.is_file() and not file_path.name.startswith('.') and
            any(str(file_path).lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS)):
            
            file_path_str = str(file_path)
            
            # Skip if already processed or scheduled
            if (event_handler._is_already_processed(file_path_str) or
                event_handler._is_already_scheduled(file_path_str)):
                continue
                
            # Get the next available time slot and schedule
            scheduled_time = schedule_iterator.next_slot()
            event_handler._schedule_image(file_path_str, scheduled_time)
    
    # Set up the file system observer
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=False)
    
    logger.info(f"Starting to watch directory: {watch_path}")
    observer.start()
    
    try:
        while True:
            show_idle_animation()
            time.sleep(2)
            
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()
    return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <directory_to_watch>")
        sys.exit(1)
    
    watch_directory(sys.argv[1])