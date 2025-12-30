#!/usr/bin/env python3
"""Test script for the InstaPost scheduler."""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from instapost.daemons.scheduler import (
    load_processed,
    save_processed,
    SCHEDULE_FILE,
    PROCESSED_FILE,
    IMAGES_DIR
)
from instapost.utils import load_json as load_schedule

def setup_test_environment():
    """Set up test environment with sample files."""
    # Create test images directory
    IMAGES_DIR.mkdir(exist_ok=True)
    
    # Create a test image
    test_image = IMAGES_DIR / "test_image.jpg"
    test_image.touch()
    
    # Create test schedule
    schedule = [
        {
            "filename": "test_image.jpg",
            "time": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "original_path": str(test_image),
            "caption": "Test post from scheduler"
        }
    ]
    
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule, f, indent=2)
    
    # Ensure processed file exists but is empty
    with open(PROCESSED_FILE, 'w') as f:
        json.dump([], f)
    
    return test_image

def cleanup_test_environment():
    """Clean up test environment."""
    if SCHEDULE_FILE.exists():
        SCHEDULE_FILE.unlink()
    if PROCESSED_FILE.exists():
        PROCESSED_FILE.unlink()
    if IMAGES_DIR.exists():
        shutil.rmtree(IMAGES_DIR)

def test_scheduler():
    """Test the scheduler functionality."""
    print("Setting up test environment...")
    test_image = setup_test_environment()
    
    try:
        print("Running scheduler test...")
        from instapost.daemons.scheduler import run_scheduler
        
        # Run the scheduler once
        run_scheduler()
        
        # Check if the file was processed
        processed = load_processed()
        if not processed:
            print("❌ Test failed: No files were processed")
            return False
            
        if processed[0]['filename'] != "test_image.jpg":
            print(f"❌ Test failed: Unexpected filename in processed list: {processed[0]['filename']}")
            return False
            
        print("✅ Test passed: File was processed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("Cleaning up test environment...")
        cleanup_test_environment()

if __name__ == "__main__":
    if test_scheduler():
        sys.exit(0)
    else:
        sys.exit(1)
