"""Cron-based scheduler - processes due posts using self-hosted images.

Usage: python -m instapost.cron.scheduler_cron
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from instapost.utils import load_json, save_json, PROJECT_ROOT, setup_logging
from instapost.settings import TIMEZONE
from instapost.clients.static_hosting import get_public_url

logger = setup_logging('scheduler_cron')

SCHEDULE_FILE = PROJECT_ROOT / "schedule.json"
PROCESSED_FILE = PROJECT_ROOT / "processed.json"


def get_images_dir() -> Path:
    """Get the images directory from environment or default."""
    return Path(os.getenv("IMAGES_DIR", PROJECT_ROOT / "images"))


def get_processed_dir() -> Path:
    """Get the processed directory from environment or default."""
    return Path(os.getenv("PROCESSED_DIR", PROJECT_ROOT / "processed"))


def move_to_processed(local_path: Path, timestamp: str) -> bool:
    """Move a posted file to the processed directory.

    Args:
        local_path: Path to the image file
        timestamp: ISO format timestamp for organizing by date

    Returns:
        True if moved successfully, False otherwise
    """
    if not local_path.exists():
        logger.debug(f"File already moved or doesn't exist: {local_path}")
        return True

    processed_dir = get_processed_dir()

    # Organize by date
    try:
        post_date = datetime.fromisoformat(timestamp).date()
        date_dir = processed_dir / str(post_date)
    except (ValueError, TypeError):
        date_dir = processed_dir

    date_dir.mkdir(parents=True, exist_ok=True)
    dst = date_dir / local_path.name

    try:
        shutil.move(str(local_path), str(dst))
        logger.info(f"Moved: {local_path.name} -> {date_dir.name}/")

        # Also move .txt caption file if exists
        txt_src = local_path.with_suffix('.txt')
        if txt_src.exists():
            txt_dst = date_dir / txt_src.name
            shutil.move(str(txt_src), str(txt_dst))
            logger.info(f"Moved caption: {txt_src.name}")

        return True
    except Exception as e:
        logger.error(f"Failed to move {local_path.name}: {e}")
        return False


def run_command(cmd: list, cwd: Optional[Path] = None, verbose: bool = False) -> tuple:
    """Run a shell command and return success status and output."""
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = str(PROJECT_ROOT)

        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
            env=env
        )

        if result.returncode != 0:
            error_msg = result.stderr or f"Command failed with return code {result.returncode}"
            logger.error(f"Command failed: {error_msg}")
            return False, error_msg

        return True, result.stdout.strip()

    except Exception as e:
        error_msg = f"Error running command: {e}"
        logger.error(error_msg)
        return False, error_msg


def get_caption(local_path: Path) -> str:
    """Get caption from IPTC metadata or .txt file."""
    caption = ''

    # Try reading from IPTC metadata first
    try:
        from iptcinfo3 import IPTCInfo
        info = IPTCInfo(str(local_path))
        iptc_caption = info.get('caption/abstract')
        if iptc_caption:
            if isinstance(iptc_caption, bytes):
                caption = iptc_caption.decode('utf-8', errors='ignore').strip()
            else:
                caption = str(iptc_caption).strip()
            if caption:
                logger.info(f"Using caption from IPTC metadata ({len(caption)} chars)")
                return caption
    except Exception as e:
        logger.debug(f"No IPTC caption found: {e}")

    # Fall back to .txt file
    txt_file = local_path.with_suffix('.txt')
    if txt_file.exists():
        try:
            caption = txt_file.read_text(encoding='utf-8').strip()
            if caption:
                logger.info(f"Using caption from .txt file ({len(caption)} chars)")
        except Exception as e:
            logger.warning(f"Failed to read .txt file: {e}")

    return caption


def process_file(entry: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Process a single scheduled file using self-hosted URL.

    Args:
        entry: Dictionary containing 'filename', 'time', and 'original_path' keys

    Returns:
        dict: Result with 'filename', 'time', 'url', and 'timestamp' keys
        None: If processing failed
    """
    filename = entry['filename']
    verbose = os.environ.get('VERBOSE', '').lower() in ('1', 'true', 'yes')

    # Get file path
    local_path = None
    if 'original_path' in entry:
        local_path = Path(entry['original_path'])

    if not local_path or not local_path.exists():
        images_dir = get_images_dir()
        images_path = images_dir / filename
        if images_path.exists():
            local_path = images_path
        else:
            local_path = Path(filename)

    logger.info(f"Starting processing for: {local_path}")
    if not local_path.exists():
        logger.error(f"File not found: {local_path}")
        return None

    try:
        # 1. Generate self-hosted URL (no upload needed!)
        image_url = get_public_url(filename)
        logger.info(f"Using self-hosted URL: {image_url}")

        # 2. Get caption from IPTC or .txt file
        caption = get_caption(local_path)

        # 3. Post to Instagram using clients/instagram.py
        logger.info(f"Posting {image_url} to Instagram...")

        cmd = [
            sys.executable,
            '-m', 'instapost.clients.instagram',
            image_url,
            '--caption', caption,
        ]
        if verbose:
            cmd.append('--verbose')

        success, output = run_command(cmd, cwd=PROJECT_ROOT, verbose=True)
        if not success:
            logger.error(f"Failed to post {filename} to Instagram: {output.strip()}")
            return None

        # Extract the Instagram post URL from the output
        post_url = None
        for line in output.split('\n'):
            if 'Instagram post URL:' in line:
                post_url = line.split('Instagram post URL:')[1].strip()
                break
            elif 'https://www.instagram.com/p/' in line:
                post_url = line.strip()
                break

        if not post_url:
            logger.error(f"Failed to extract post URL from output")
            return None

        logger.info(f"Successfully posted to Instagram: {post_url}")

        timestamp = datetime.now().isoformat()

        # Move file to processed directory immediately
        move_to_processed(local_path, timestamp)

        return {
            'filename': filename,
            'time': entry['time'],
            'url': post_url,
            'timestamp': timestamp
        }

    except Exception as e:
        logger.error(f"Error processing {filename}: {e}", exc_info=True)
        return None


def load_processed() -> List[Dict]:
    """Load the processed files list."""
    try:
        data = load_json(PROCESSED_FILE)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Could not load processed files: {e}")
        return []


def save_processed(processed: List[Dict]) -> None:
    """Save the processed files list."""
    try:
        save_json(PROCESSED_FILE, processed)
    except Exception as e:
        logger.error(f"Failed to save processed files: {e}")


def process_due_posts():
    """Process all posts that are due for posting."""
    # Ensure required files exist
    if not SCHEDULE_FILE.exists():
        save_json(SCHEDULE_FILE, [])
    if not PROCESSED_FILE.exists():
        save_json(PROCESSED_FILE, [])

    now = datetime.now(TIMEZONE)
    scheduled = load_json(SCHEDULE_FILE)
    processed = load_processed()

    if not isinstance(scheduled, list):
        logger.error("Invalid schedule format")
        return

    if not scheduled:
        logger.info("No scheduled posts")
        return

    processed_filenames = {p['filename'] for p in processed if isinstance(p, dict)}
    posts_processed = 0

    for entry in scheduled:
        if not isinstance(entry, dict):
            continue

        filename = entry.get('filename')
        if not filename:
            continue

        # Skip if already processed
        if filename in processed_filenames:
            continue

        # Parse scheduled time
        try:
            scheduled_time = datetime.fromisoformat(entry['time']).replace(tzinfo=TIMEZONE)
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Invalid time format in entry: {entry}")
            continue

        # Process if due (within 2 minute window for cron timing)
        if scheduled_time <= now:
            logger.info(f"Processing due post: {filename} (scheduled for {scheduled_time})")

            result = process_file(entry)
            if result:
                processed.append(result)
                save_processed(processed)
                processed_filenames.add(filename)
                posts_processed += 1
                logger.info(f"Successfully processed {filename}")
            else:
                logger.error(f"Failed to process {filename}")

    if posts_processed > 0:
        logger.info(f"Processed {posts_processed} post(s)")
    else:
        logger.info("No posts due for processing")


def main():
    """Main entry point for cron execution."""
    logger.info("Scheduler cron job started")
    try:
        process_due_posts()
    except Exception as e:
        logger.error(f"Scheduler cron job failed: {e}", exc_info=True)
        sys.exit(1)
    logger.info("Scheduler cron job completed")


if __name__ == '__main__':
    main()
