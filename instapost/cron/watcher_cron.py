"""Cron-based watcher - scans for new images and schedules them.

Usage: python -m instapost.cron.watcher_cron
"""

import sys
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
from PIL import Image

from instapost.utils import load_json, save_json, PROJECT_ROOT, setup_logging
from instapost.settings import TIMEZONE, WEEKLY_SCHEDULE
from instapost.validation import validate_image_file, get_image_info
from instapost.schedule_utils import add_to_schedule, ScheduleValidationError

logger = setup_logging('watcher_cron')

# Instagram only supports these formats
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png']
SCHEDULE_FILE = "schedule.json"
STATE_FILE = ".watcher_state.json"


class ScheduleIterator:
    """Iterator that provides the next available time slot for scheduling."""

    def __init__(self):
        self.weekly_schedule = {i: [] for i in range(7)}

        if isinstance(WEEKLY_SCHEDULE, dict):
            for day, times in WEEKLY_SCHEDULE.items():
                if isinstance(times, list):
                    self.weekly_schedule[int(day)] = sorted(times)
        else:
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

        for day in self.weekly_schedule:
            self.weekly_schedule[day].sort()

    def _get_last_scheduled_time(self):
        schedule = load_json(SCHEDULE_FILE)
        if not isinstance(schedule, list) or not schedule:
            return None

        try:
            last_time = max(
                datetime.fromisoformat(entry['time']).replace(tzinfo=TIMEZONE)
                for entry in schedule
                if 'time' in entry
            )
            return last_time
        except (ValueError, KeyError):
            return None

    def next_slot(self) -> str:
        now = datetime.now(TIMEZONE)
        last_time = self._get_last_scheduled_time()

        if not last_time:
            current_date = now.date()
            for _ in range(14):
                weekday = current_date.weekday()
                if self.weekly_schedule[weekday]:
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

        last_date = last_time.date()
        last_weekday = last_time.weekday()
        last_time_str = last_time.strftime('%H:%M')

        if self.weekly_schedule[last_weekday]:
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

        current_date = last_date + timedelta(days=1)
        for _ in range(14):
            weekday = current_date.weekday()
            if self.weekly_schedule[weekday]:
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


def get_images_dir() -> Path:
    """Get the images directory from environment or default."""
    return Path(os.getenv("IMAGES_DIR", PROJECT_ROOT / "images"))


def load_state() -> set:
    """Load set of known files from state file."""
    state_path = PROJECT_ROOT / STATE_FILE
    if state_path.exists():
        data = load_json(STATE_FILE)
        if isinstance(data, list):
            return set(data)
    return set()


def save_state(files: set):
    """Save set of known files to state file."""
    save_json(STATE_FILE, sorted(list(files)))


def resize_image_if_needed(file_path: Path, max_size_mb: float = 8) -> bool:
    """Resize image if it exceeds the maximum size."""
    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    if file_size_mb <= max_size_mb:
        return False

    logger.info(f"Image size ({file_size_mb:.1f}MB) exceeds {max_size_mb}MB limit. Resizing...")

    try:
        img = Image.open(file_path)
        scale_factor = (max_size_mb * 0.9 / file_size_mb) ** 0.5
        new_width = int(img.width * scale_factor)
        new_height = int(img.height * scale_factor)

        logger.info(f"Resizing from {img.width}x{img.height} to {new_width}x{new_height}")

        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        temp_file = tempfile.NamedTemporaryFile(
            suffix=file_path.suffix,
            delete=False,
            mode='wb'
        )
        temp_path = Path(temp_file.name)

        if file_path.suffix.lower() in ['.jpg', '.jpeg']:
            img_resized.save(temp_path, 'JPEG', quality=85, optimize=True)
        elif file_path.suffix.lower() == '.png':
            img_resized.save(temp_path, 'PNG', optimize=True)
        else:
            img_resized.save(temp_path)

        temp_file.close()
        shutil.move(str(temp_path), str(file_path))

        new_size_mb = file_path.stat().st_size / (1024 * 1024)
        logger.info(f"Image resized to {new_size_mb:.1f}MB")
        return True

    except Exception as e:
        logger.error(f"Failed to resize image {file_path}: {e}")
        return False


def write_caption_to_iptc(image_path: Path, caption: str) -> bool:
    """Write caption to IPTC Caption-Abstract metadata field."""
    try:
        from iptcinfo3 import IPTCInfo
        info = IPTCInfo(str(image_path))
        info['caption/abstract'] = caption
        info.save()
        logger.info(f"Caption written to IPTC metadata ({len(caption)} chars)")
        return True
    except Exception as e:
        logger.warning(f"Failed to write IPTC metadata: {e}")
        return False


def generate_caption(image_path: Path):
    """Generate caption for image if .txt file doesn't exist."""
    txt_file = image_path.with_suffix('.txt')

    if txt_file.exists():
        logger.info(f"Caption file already exists: {txt_file.name}")
        # Still write to IPTC if not already there
        try:
            caption = txt_file.read_text(encoding='utf-8').strip()
            if caption:
                write_caption_to_iptc(image_path, caption)
        except Exception:
            pass
        return

    logger.info(f"Generating caption for {image_path.name}...")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'instapost.generate_captions', str(image_path)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info(f"Caption generated: {txt_file.name}")
            if txt_file.exists():
                try:
                    caption = txt_file.read_text(encoding='utf-8').strip()
                    if caption:
                        write_caption_to_iptc(image_path, caption)
                except Exception as e:
                    logger.warning(f"Failed to read caption for IPTC write: {e}")
        else:
            logger.warning(f"Failed to generate caption: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.warning(f"Caption generation timed out for {image_path.name}")
    except Exception as e:
        logger.warning(f"Error generating caption: {e}")


def process_new_image(image_path: Path, schedule_iterator: ScheduleIterator) -> bool:
    """Process a new image: validate, resize, generate caption, schedule."""
    try:
        # Resize if needed before validation
        resize_image_if_needed(image_path)

        # Validate image
        is_valid, error = validate_image_file(str(image_path))
        if not is_valid:
            logger.warning(f"Image validation failed for {image_path.name}: {error}")
            info = get_image_info(str(image_path))
            logger.debug(f"Image info: {info['width']}x{info['height']}, "
                        f"{info['size_mb']:.2f}MB, aspect ratio: {info['aspect_ratio']:.2f}")
            return False

        # Generate caption if needed
        generate_caption(image_path)

        # Get next time slot and schedule
        scheduled_time = schedule_iterator.next_slot()

        add_to_schedule(
            filename=image_path.name,
            scheduled_time=scheduled_time,
            original_path=str(image_path)
        )

        scheduled_time_str = datetime.fromisoformat(scheduled_time).strftime("%Y-%m-%d %H:%M")
        logger.info(f"Scheduled {image_path.name} for {scheduled_time_str}")
        return True

    except ScheduleValidationError as e:
        logger.error(f"Schedule validation failed for {image_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to process {image_path}: {e}")
        return False


def scan_and_schedule():
    """Scan images directory and schedule any new files."""
    images_dir = get_images_dir()

    if not images_dir.exists():
        logger.error(f"Images directory does not exist: {images_dir}")
        return

    # Load known state
    known_files = load_state()

    # Get current image files
    current_files = set()
    for ext in SUPPORTED_EXTENSIONS:
        for f in images_dir.glob(f"*{ext}"):
            if not f.name.startswith('.'):
                current_files.add(f.name)
        for f in images_dir.glob(f"*{ext.upper()}"):
            if not f.name.startswith('.'):
                current_files.add(f.name)

    # Get already scheduled/processed files
    scheduled_files = {e['filename'] for e in load_json(SCHEDULE_FILE) if isinstance(e, dict)}
    processed_files = {e['filename'] for e in load_json("processed.json") if isinstance(e, dict)}

    # Find truly new files
    new_files = current_files - known_files - scheduled_files - processed_files

    if not new_files:
        logger.info("No new images to process")
        save_state(known_files | current_files)
        return

    logger.info(f"Found {len(new_files)} new image(s) to process")

    schedule_iterator = ScheduleIterator()

    for filename in sorted(new_files):
        file_path = images_dir / filename
        if file_path.exists():
            process_new_image(file_path, schedule_iterator)

    # Update state with all known files
    save_state(known_files | current_files)


def main():
    """Main entry point for cron execution."""
    logger.info("Watcher cron job started")
    try:
        scan_and_schedule()
    except Exception as e:
        logger.error(f"Watcher cron job failed: {e}")
        sys.exit(1)
    logger.info("Watcher cron job completed")


if __name__ == '__main__':
    main()
