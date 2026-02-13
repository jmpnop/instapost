import sys
import time
import shutil
from pathlib import Path
from instapost.utils import load_json, setup_logging, show_idle_animation, PROJECT_ROOT, ensure_single_instance
from instapost.version import get_version_string
from instapost.daemon_base import ResilientDaemon

logger = setup_logging('mover')

PROCESSED_FILE = "processed.json"


class MoverDaemon(ResilientDaemon):
    """Resilient mover daemon that never dies on errors."""

    def __init__(self, source_dir, dest_dir):
        """Initialize mover daemon with 5-second check interval."""
        super().__init__(
            name="mover",
            logger=logger,
            check_interval=0,  # We handle sleep ourselves
            heartbeat_enabled=True
        )
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.src_path = None
        self.dst_path = None
        self.moved = set()

    def setup(self):
        """One-time setup: validate directories."""
        logger.info(f"📦 {get_version_string()}")

        # Ensure only one instance is running
        ensure_single_instance('mover')

        # Validate source directory
        self.src_path = Path(self.source_dir)
        if not self.src_path.exists():
            self.src_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created source directory: {self.source_dir}")
        elif not self.src_path.is_dir():
            raise ValueError(f"Source directory does not exist or is not a directory: {self.source_dir}")

        # Validate/create destination directory
        self.dst_path = Path(self.dest_dir)
        if not self.dst_path.exists():
            self.dst_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created destination directory: {self.dest_dir}")

    def work(self):
        """Move processed files from source to destination."""
        processed = load_json(PROCESSED_FILE)
        for entry in processed:
            if entry['url'] is not None and entry['filename'] not in self.moved:
                src = self.src_path / entry['filename']
                dst = self.dst_path / entry['filename']
                if src.exists():
                    shutil.move(str(src), str(dst))
                    self.moved.add(entry['filename'])
                    logger.info(f"Moved file: {entry['filename']}")

        show_idle_animation()
        time.sleep(5)

    def cleanup(self):
        """Cleanup before shutdown."""
        logger.info("Mover cleanup complete")


def move_processed_files(source_dir, dest_dir):
    """Move processed files (legacy function for backward compatibility)."""
    daemon = MoverDaemon(source_dir, dest_dir)
    return daemon.run()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <source_dir> <dest_dir>")
        sys.exit(1)

    daemon = MoverDaemon(sys.argv[1], sys.argv[2])
    sys.exit(daemon.run())
