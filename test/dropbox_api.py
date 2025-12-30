#!/usr/bin/env python3
"""Test script for Dropbox API integration."""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from instapost.config import load_settings
from instapost.clients.dropbox import DropboxClient


def test_dropbox_upload(image_path):
    """Test Dropbox upload with detailed reporting."""
    print("\n=== Testing Dropbox Upload ===")

    try:
        # Load settings
        print("Loading configuration...")
        settings = load_settings()

        print(f"Dropbox App Key: {settings.dropbox.app_key[:10]}...")
        print(f"Dropbox Folder: {settings.dropbox.folder_path}")

        # Initialize client
        print("\nInitializing Dropbox client...")
        client = DropboxClient(settings.dropbox)

        # Test file existence
        image_path = Path(image_path)
        if not image_path.exists():
            print(f"❌ Error: File not found: {image_path}")
            return False

        print(f"Image file: {image_path}")
        print(f"File size: {image_path.stat().st_size / 1024:.2f} KB")

        # Upload file
        print("\nUploading to Dropbox...")
        file_metadata = client.upload_image(str(image_path))
        print(f"✅ Upload successful!")
        print(f"   Path: {file_metadata.path_display}")
        print(f"   Size: {file_metadata.size} bytes")

        # Get shared link
        print("\nGenerating shared link...")
        shared_link = client.get_shared_link(file_metadata)
        print(f"✅ Shared link created!")
        print(f"   URL: {shared_link}")

        # Verify it's a raw link
        if "raw=1" in shared_link:
            print("✅ Link is in raw format (ready for Instagram)")
        else:
            print("⚠️  Warning: Link is not in raw format")

        print("\n=== All Dropbox tests passed! ===")
        return True

    except FileNotFoundError as e:
        print(f"❌ File error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during Dropbox test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dropbox_client_only():
    """Test Dropbox client initialization without upload."""
    print("\n=== Testing Dropbox Client Initialization ===")

    try:
        settings = load_settings()
        client = DropboxClient(settings.dropbox)

        print("✅ Dropbox client initialized successfully")
        print(f"   Configured folder: {settings.dropbox.folder_path}")

        return True

    except Exception as e:
        print(f"❌ Error initializing Dropbox client: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Dropbox upload functionality")
    parser.add_argument('--file', type=str, help='Path to image file to upload (optional)')
    parser.add_argument('--client-only', action='store_true', help='Only test client initialization')

    args = parser.parse_args()

    if args.client_only:
        success = test_dropbox_client_only()
    elif args.file:
        success = test_dropbox_upload(args.file)
    else:
        print("Testing Dropbox client initialization (use --file to test upload)")
        success = test_dropbox_client_only()

    sys.exit(0 if success else 1)
