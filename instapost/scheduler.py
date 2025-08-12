import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from instapost.utils import load_json, save_json, PROJECT_ROOT, setup_logger

# Set up logging
logger = setup_logger('scheduler')

# Constants
SCHEDULE_FILE = PROJECT_ROOT / "schedule.json"
PROCESSED_FILE = PROJECT_ROOT / "processed.json"
IMAGES_DIR = PROJECT_ROOT / "images"

# Ensure required directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

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
            
        success, output = run_command(cmd, cwd=PROJECT_ROOT, verbose=verbose)
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

def load_schedule() -> List[Dict]:
    """Load the schedule from file."""
    try:
        return load_json(SCHEDULE_FILE)
    except Exception as e:
        logger.error(f"Failed to load schedule: {e}")
        return []

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
    """Run the scheduler loop to process scheduled posts."""
    if not os.path.exists(SCHEDULE_FILE):
        logger.error(f"Missing required file: {SCHEDULE_FILE}")
        return
        
    if not os.path.exists(PROCESSED_FILE):
        save_json(PROCESSED_FILE, [])
    
    logger.info("Running scheduler loop")
    
    try:
        while True:
            try:
                # Load schedule and processed files
                schedule = load_schedule()
                processed = load_processed()
                
                # Get set of already processed filenames for faster lookup
                processed_files = {item['filename'] for item in processed}
                now = datetime.now().isoformat()
                
                logger.debug(f"Checking schedule at {now}")
                logger.debug(f"Found {len(schedule)} scheduled items, {len(processed_files)} already processed")
                
                # Process files that are due
                for entry in schedule:
                    filename = entry.get('filename')
                    scheduled_time = entry.get('time')
                    
                    if not filename or not scheduled_time:
                        logger.warning(f"Invalid schedule entry: {entry}")
                        continue
                        
                    if filename in processed_files:
                        continue
                        
                    if scheduled_time <= now:
                        logger.info(f"Processing scheduled post: {filename} (scheduled for {scheduled_time})")
                        result = process_file(entry)
                        
                        if result:
                            processed.append(result)
                            save_processed(processed)
                            logger.info(f"Successfully processed {filename}")
                        else:
                            logger.error(f"Failed to process {filename}")
                
                # Sleep for a while before checking again
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
                
            except Exception as e:
                logger.error(f"Error in scheduler: {e}", exc_info=True)
                time.sleep(300)  # Wait 5 minutes before retrying on error
                
    except Exception as e:
        logger.critical(f"Fatal error in scheduler: {e}", exc_info=True)
    finally:
        logger.info("Scheduler stopped")

def main():
    """Main entry point for the scheduler."""
    try:
        run_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error in scheduler: {e}", exc_info=True)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())