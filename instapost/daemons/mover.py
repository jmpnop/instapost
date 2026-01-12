import sys
import time
import shutil
from pathlib import Path
from instapost.utils import load_json, setup_logging, show_idle_animation, PROJECT_ROOT, ensure_single_instance
from instapost.version import get_version_string

logger = setup_logging('mover')

PROCESSED_FILE = "processed.json"

def move_processed_files(source_dir, dest_dir):
    logger.info(f"📦 {get_version_string()}")
    # Ensure only one instance is running
    ensure_single_instance('mover')

    src_path = Path(source_dir)
    dst_path = Path(dest_dir)

    if not src_path.exists() or not src_path.is_dir():
        logger.error(f"Source directory does not exist or is not a directory: {source_dir}")
        return

    if not dst_path.exists():
        try:
            dst_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created destination directory: {dest_dir}")
        except Exception as e:
            logger.error(f"Failed to create destination directory: {e}")
            return

    moved = set()
    while True:
        try:
            processed = load_json(PROCESSED_FILE)
            for entry in processed:
                if entry['url'] is not None and entry['filename'] not in moved:
                    src = src_path / entry['filename']
                    dst = dst_path / entry['filename']
                    if src.exists():
                        shutil.move(str(src), str(dst))
                        moved.add(entry['filename'])
                        logger.info(f"Moved file: {entry['filename']}")
        except Exception as e:
            logger.error(f"Error moving files: {e}")
        show_idle_animation()
        time.sleep(5)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <source_dir> <dest_dir>")
        sys.exit(1)
    move_processed_files(sys.argv[1], sys.argv[2])
