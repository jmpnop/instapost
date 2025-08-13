import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

from instapost.utils import load_json, save_json, PROJECT_ROOT, setup_logger, ensure_single_instance, show_idle_animation
from instapost.settings import TIMEZONE, WEEKLY_SCHEDULE

# Set up logging
logger = setup_logger('scheduler')

# Constants
SCHEDULE_FILE = PROJECT_ROOT / "schedule.json"
PROCESSED_FILE = PROJECT_ROOT / "processed.json"
IMAGES_DIR = PROJECT_ROOT / "images"

def run_scheduler():
    """Run the scheduling loop."""
    logger.info("🚀 Running scheduler loop")
    logger.info("👀 Watching for scheduled posts...")
    
    # Ensure required files exist
    if not os.path.exists(SCHEDULE_FILE):
        save_json(SCHEDULE_FILE, [])
    if not os.path.exists(PROCESSED_FILE):
        save_json(PROCESSED_FILE, [])
    
    try:
        while True:
            current_time = datetime.now(TIMEZONE)
            logger.debug(f"Checking schedule at {current_time}")
            
            # Process any scheduled posts that are due
            process_scheduled_posts()
            
            # Show idle animation
            show_idle_animation()
            
            # Always check at the start of the next minute
            next_minute = (current_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_seconds = (next_minute - current_time).total_seconds()
            
            if sleep_seconds > 0:
                logger.debug(f"Sleeping for {sleep_seconds:.1f} seconds")
                # Show idle animation while waiting
                start_time = time.time()
                while time.time() - start_time < min(sleep_seconds, 60):
                    show_idle_animation()
            else:
                # In case we're already past the next minute
                show_idle_animation()
                time.sleep(1)
            
            # Process any scheduled posts that are due
            process_scheduled_posts()
            
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Error in scheduler: {e}", exc_info=True)
    finally:
        logger.info("Scheduler stopped")

# [Rest of the file remains the same...]

# Ensure required directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Timezone and schedule configuration

# Test mode - overrides the weekly schedule when enabled
TEST_MODE = os.getenv('TEST_MODE', 'False').lower() in ('true', '1', 't')
if TEST_MODE:
    # In test mode, we'll process past-due entries immediately
    logger.info("🛠️  TEST MODE: Will process past-due entries immediately")
    # Set test schedule for 5 minutes ahead
    test_time = (datetime.now(TIMEZONE) + timedelta(minutes=5)).strftime("%H:%M")
    test_weekday = datetime.now(TIMEZONE).weekday()
    WEEKLY_SCHEDULE = {test_weekday: [test_time]}
else:
    logger.info("🏭 Running in PRODUCTION mode with weekly schedule")

def should_process_immediately(scheduled_time: datetime) -> bool:
    """Determine if a post should be processed immediately in test mode."""
    if not TEST_MODE:
        return False
    # In test mode, process all posts immediately regardless of scheduled time
    logger.info(f"⏰ Processing post immediately in test mode (scheduled for {scheduled_time})")
    return True

def get_next_scheduled_time() -> str:
    """Calculate the next available scheduled time based on the weekly schedule.
    
    Returns:
        str: ISO formatted datetime string of the next available time slot
    """
    now = datetime.now(TIMEZONE)
    
    # Load existing schedule to avoid double-booking
    try:
        schedule = load_json(SCHEDULE_FILE)
        if not isinstance(schedule, list):
            schedule = []
        scheduled_times = {datetime.fromisoformat(entry['time']).replace(tzinfo=TIMEZONE) for entry in schedule}
    except Exception as e:
        logger.warning(f"Failed to load schedule: {e}")
        scheduled_times = set()

    # Check for the next slot starting from today
    for offset in range(7):
        candidate_day = now + timedelta(days=offset)
        weekday = candidate_day.weekday()
        
        if weekday not in WEEKLY_SCHEDULE:
            continue
            
        for time_str in WEEKLY_SCHEDULE[weekday]:
            # Create a timezone-aware datetime for this slot
            scheduled_time = TIMEZONE.localize(datetime.strptime(
                f"{candidate_day.date()} {time_str}", 
                "%Y-%m-%d %H:%M"
            ))
            
            # Skip if this time is in the past or already scheduled
            if scheduled_time <= now or scheduled_time in scheduled_times:
                continue
                
            # Found an available slot
            return scheduled_time.isoformat()
    
    # Fallback: if no available slots found, find the next week's first available slot
    for offset in range(7, 14):
        candidate_day = now + timedelta(days=offset)
        weekday = candidate_day.weekday()
        
        if weekday not in WEEKLY_SCHEDULE:
            continue
            
        # Return the first available time slot next week
        time_str = WEEKLY_SCHEDULE[weekday][0]
        scheduled_time = TIMEZONE.localize(datetime.strptime(
            f"{candidate_day.date()} {time_str}", 
            "%Y-%m-%d %H:%M"
        ))
        return scheduled_time.isoformat()
        
    # Last resort: return now + 1 hour if no schedule is available
    return (now + timedelta(hours=1)).isoformat()

# Configuration is loaded via environment variables in the subprocesses

def run_command(cmd: list, cwd: Optional[Path] = None, verbose: bool = False) -> tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        if verbose:
            logger.debug(f"Running command: {' '.join(str(c) for c in cmd)}")
            
        # Create environment with PYTHONPATH set to project root
        env = os.environ.copy()
        env['PYTHONPATH'] = str(PROJECT_ROOT)
        
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else str(PROJECT_ROOT),  # Run from project root
            capture_output=True,
            text=True,
            check=False,
            env=env
        )
        
        if verbose:
            if result.stdout:
                logger.debug(f"stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"stderr: {result.stderr}")
                
        if result.returncode != 0:
            error_msg = result.stderr or f"Command failed with return code {result.returncode}"
            logger.error(f"Command failed: {error_msg}")
            return False, error_msg
            
        return True, result.stdout.strip()
        
    except Exception as e:
        error_msg = f"Error running command: {e}"
        logger.error(error_msg)
        return False, error_msg


def process_file(entry: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Process a single scheduled file using subprocess calls.
    
    Args:
        entry: Dictionary containing 'filename', 'time', and optionally 'original_path' keys
        
    Returns:
        dict: Result with 'filename', 'time', 'url', and 'timestamp' keys
        None: If processing failed
    """
    filename = entry['filename']
    verbose = os.environ.get('VERBOSE', '').lower() in ('1', 'true', 'yes')
    
    # Try to get the file path in this order:
    # 1. original_path from the entry
    # 2. filename as a path relative to the project's images directory
    # 3. filename as an absolute path
    local_path = None
    if 'original_path' in entry:
        local_path = Path(entry['original_path'])
    
    if not local_path or not local_path.exists():
        # Try the images directory
        images_path = PROJECT_ROOT / 'images' / filename
        if images_path.exists():
            local_path = images_path
        else:
            # Try the filename as an absolute path
            local_path = Path(filename)
    
    logger.info(f"Starting processing for: {local_path}")
    if not local_path.exists():
        logger.error(f"File not found: {local_path}")
        return None
    
    try:
        # 1. Upload to Dropbox using db_upload.py
        logger.info(f"Uploading {filename} to Dropbox...")
        cmd = [
            sys.executable,  # Use the same Python interpreter
            str(PROJECT_ROOT / 'instapost' / 'db_upload.py'),
            '--file', str(local_path),  # Changed from --image to --file
        ]
        if verbose:
            cmd.append('--verbose')
            
        success, output = run_command(cmd, cwd=PROJECT_ROOT, verbose=verbose)
        if not success:
            logger.error(f"Failed to upload {filename} to Dropbox")
            return None
            
        if verbose:
            logger.debug(f"db_upload.py output:\n{output}")
            
        # Extract the shared URL from the output
        shared_url = None
        lines = output.split('\n')
        for i, line in enumerate(lines):
            if 'Raw Image URL for posting:' in line:
                # The URL is on the next line after the label
                if i + 1 < len(lines):
                    shared_url = lines[i+1].strip()
                    break
            elif line.startswith('http'):
                # Fallback: if we see a URL, use it
                shared_url = line.strip()
                break
                
        if verbose and shared_url:
            logger.debug(f"Extracted shared URL: {shared_url}")
                
        if not shared_url:
            logger.error(f"Failed to extract shared URL from db_upload.py output")
            return None
            
        logger.info(f"Successfully uploaded to Dropbox: {shared_url}")
        
        # 2. Post to Instagram using post.py
        logger.info(f"Posting {shared_url} to Instagram...")
        caption = entry.get('caption', '')
        
        cmd = [
            sys.executable,  # Use the same Python interpreter
            str(PROJECT_ROOT / 'instapost' / 'post.py'),
            shared_url,  # Image URL as positional argument
            '--caption', caption,
        ]
        if verbose:
            cmd.append('--verbose')
            
        success, output = run_command(cmd, cwd=PROJECT_ROOT, verbose=True)  # Enable verbose logging for Instagram posts
        if not success:
            # The error message is now in the output, so we can log it directly
            logger.error(f"Failed to post {filename} to Instagram: {output.strip()}")
            return None
            
        # Extract the Instagram post URL from the output
        post_url = None
        for line in output.split('\n'):
            if 'Instagram post URL:' in line:
                post_url = line.split('Instagram post URL:')[1].strip()
                break
            elif 'https://www.instagram.com/p/' in line:
                # Fallback: if we see an Instagram URL, use it
                post_url = line.strip()
                break
                
        if not post_url:
            logger.error(f"Failed to extract post URL from post.py output")
            return None
            
        logger.info(f"Successfully posted to Instagram: {post_url}")
        
        return {
            'filename': filename,
            'time': entry['time'],
            'url': post_url,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing {filename}: {e}", exc_info=True)
        return None  # Return None to indicate failure

# Track the last known schedule state
last_schedule_count = 0

def process_scheduled_posts():
    """Process any scheduled posts that are due."""
    global last_schedule_count
    
    try:
        # Load current state
        scheduled = load_json(SCHEDULE_FILE)
        processed = load_processed()
        
        # Verify schedule file exists and is valid
        if not isinstance(scheduled, list):
            logger.error("❌ Invalid schedule format - resetting to empty list")
            scheduled = []
            save_json(SCHEDULE_FILE, scheduled)
            
        if not scheduled:
            if last_schedule_count > 0:
                logger.info("📭 Schedule is now empty")
                last_schedule_count = 0
            return
            
        # Check for new entries
        current_count = len(scheduled)
        if current_count > last_schedule_count:
            new_entries = current_count - last_schedule_count
            logger.info(f"📬 Detected {new_entries} new scheduled {'entry' if new_entries == 1 else 'entries'}")
            for entry in scheduled[-new_entries:]:  # Only show the new entries
                if not all(key in entry for key in ['filename', 'time', 'original_path']):
                    logger.warning(f"⚠️  Invalid entry format: {entry}")
                    continue
                try:
                    scheduled_time = datetime.fromisoformat(entry['time']).replace(tzinfo=TIMEZONE)
                    logger.info(f"   • {entry['filename']} scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    # Verify file exists
                    if not os.path.exists(entry['original_path']):
                        logger.error(f"❌ File not found: {entry['original_path']}")
                except (ValueError, KeyError) as e:
                    logger.error(f"❌ Invalid entry data: {e}")
                    
        last_schedule_count = current_count
        logger.debug(f"🔍 Found {len(scheduled)} scheduled posts to check")
        
        now = datetime.now(TIMEZONE)
        processed_filenames = {p['filename'] for p in processed} if processed else set()
        
        # Process entries that are due and not already processed
        for entry in scheduled[:]:  # Create a copy to safely modify the list
            try:
                filename = entry.get('filename')
                original_path = entry.get('original_path')
                
                # Skip if required fields are missing
                if not all([filename, original_path, 'time' in entry]):
                    logger.error(f"❌ Missing required fields in entry: {entry}")
                    scheduled.remove(entry)
                    continue
                
                # Verify file exists
                if not os.path.exists(original_path):
                    logger.error(f"❌ File not found, removing from schedule: {original_path}")
                    scheduled.remove(entry)
                    continue
                    
                # Parse scheduled time
                try:
                    scheduled_time = datetime.fromisoformat(entry['time']).replace(tzinfo=TIMEZONE)
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Invalid time format in entry, removing: {entry}")
                    scheduled.remove(entry)
                    continue
                
                # Check if already processed
                if filename in processed_filenames:
                    logger.info(f"⏩ Skipping already processed: {filename}")
                    scheduled.remove(entry)
                    continue
                
                # Process if due or in test mode
                logger.debug(f"⏱️  Checking schedule time: now={now}, scheduled={scheduled_time}, test_mode={os.getenv('TEST_MODE', 'False')}")
                if scheduled_time <= now or should_process_immediately(scheduled_time):
                    logger.info(f"📅 Processing scheduled post: {filename} (scheduled for {scheduled_time})")
                    logger.debug(f"📂 File path: {original_path}, exists: {os.path.exists(original_path)}")
                    try:
                        logger.debug("🔧 Calling process_file...")
                        result = process_file(entry)
                        if result:
                            logger.debug("✅ Process file successful, saving to processed...")
                            processed.append(result)
                            save_processed(processed)
                            logger.info(f"✅ Successfully processed {filename}")
                            logger.info(f"👁️  Posted: {result.get('url', 'No URL available')}")
                            scheduled.remove(entry)  # Remove from schedule after successful processing
                            logger.debug("📝 Schedule updated after successful processing")
                        else:
                            logger.error(f"❌ Failed to process {filename} - process_file returned None")
                    except Exception as e:
                        logger.error(f"❌ Error processing {filename}: {str(e)}", exc_info=True)
                else:
                    logger.debug(f"⏳ Not yet due: {filename} (scheduled for {scheduled_time} > {now})")
                        
            except Exception as e:
                logger.error(f"❌ Unexpected error processing entry {entry.get('filename', 'unknown')}: {e}", exc_info=True)
        
        # Save the updated schedule if any entries were removed
        if len(scheduled) < current_count:
            save_json(SCHEDULE_FILE, scheduled)
            logger.debug(f"📋 Updated schedule with {len(scheduled)} remaining entries")
            
    except Exception as e:
        logger.error(f"Error processing scheduled posts: {e}", exc_info=True)

def load_processed() -> List[Dict]:
    """Load the processed files list."""
    try:
        return load_json(PROCESSED_FILE)
    except Exception as e:
        logger.warning(f"Could not load processed files: {e}")
        return []

def save_processed(processed: List[Dict]) -> None:
    """Save the processed files list."""
    try:
        save_json(PROCESSED_FILE, processed)
    except Exception as e:
        logger.error(f"Failed to save processed files: {e}")

def run_scheduler():
    """Run the scheduling loop."""
    logger.info("🚀 Running scheduler loop")
    logger.info("👀 Watching for scheduled posts...")
    
    # Ensure required files exist
    if not os.path.exists(SCHEDULE_FILE):
        save_json(SCHEDULE_FILE, [])
    if not os.path.exists(PROCESSED_FILE):
        save_json(PROCESSED_FILE, [])
    
    try:
        while True:
            current_time = datetime.now(TIMEZONE)
            logger.debug(f"Checking schedule at {current_time}")
            
            # Process any scheduled posts that are due
            process_scheduled_posts()
            
            # Show idle animation
            show_idle_animation()
            
            # Calculate sleep time until next minute
            next_minute = (current_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_seconds = (next_minute - current_time).total_seconds()
            
            if sleep_seconds > 0:
                logger.debug(f"Sleeping for {sleep_seconds:.1f} seconds")
                # Show animation while waiting
                start_time = time.time()
                while time.time() - start_time < min(sleep_seconds, 60):
                    show_idle_animation()
                    time.sleep(2)  # Add this line
            else:
                # In case we're already past the next minute
                time.sleep(1)
                
                # Process any scheduled posts that are due
                process_scheduled_posts()
            
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Error in scheduler: {e}", exc_info=True)
    finally:
        logger.info("Scheduler stopped")

def main():
    """Main entry point for the scheduler."""
    try:
        # Ensure only one instance is running
        ensure_single_instance('scheduler')
        run_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error in scheduler: {e}", exc_info=True)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())