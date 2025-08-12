import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from .utils import load_json, save_json, setup_logging, show_idle_animation, PROJECT_ROOT

logger = setup_logging('watcher')

SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
SCHEDULE_FILE = "schedule.json"

def watch_directory(watch_dir):
    watch_path = Path(watch_dir).resolve()
    images_dir = PROJECT_ROOT / 'images'
    images_dir.mkdir(exist_ok=True)
    
    if not watch_path.exists() or not watch_path.is_dir():
        logger.error(f"Watch directory does not exist or is not a directory: {watch_dir}")
        return

    scheduled = load_json(SCHEDULE_FILE)
    seen = set(entry['filename'] for entry in scheduled)

    while True:
        try:
            for file in watch_path.iterdir():
                if file.suffix.lower() in SUPPORTED_EXTENSIONS and file.name not in seen:
                    # Copy the file to the images directory
                    dest_path = images_dir / file.name
                    try:
                        import shutil
                        shutil.copy2(file, dest_path)
                        logger.info(f"Copied {file.name} to {dest_path}")
                        
                        # Add to schedule
                        scheduled.append({
                            'filename': file.name,
                            'time': (datetime.now() + timedelta(seconds=10)).isoformat(),
                            'original_path': str(file.resolve())  # Store original path for reference
                        })
                        seen.add(file.name)
                        save_json(SCHEDULE_FILE, scheduled)
                        logger.info(f"Scheduled new file: {file.name}")
                        
                    except Exception as copy_error:
                        logger.error(f"Failed to copy {file.name} to images directory: {copy_error}")
                        continue
        except Exception as e:
            logger.error(f"Error watching directory: {e}")
        show_idle_animation()
        time.sleep(5)

if __name__ == '__main__':
    watch_directory(sys.argv[1])