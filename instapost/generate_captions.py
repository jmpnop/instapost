#!/usr/bin/env python3
"""
Generate Instagram captions for images using AI CLI.
Usage: python -m instapost.generate_captions /path/to/image/directory
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def get_caption_prompt() -> str:
    """Get caption prompt from environment variable."""
    prompt = os.getenv('CAPTION_PROMPT')
    if not prompt:
        print("Error: CAPTION_PROMPT not set in environment. Add it to .env file.", file=sys.stderr)
        sys.exit(1)
    return prompt


def generate_caption(image_path: Path) -> str:
    """Generate a caption for the given image using AI CLI."""
    prompt_template = get_caption_prompt()
    prompt = prompt_template.format(image_path=image_path.resolve())

    result = subprocess.run(
        ['claude', '-p', prompt],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"AI CLI error: {result.stderr}")

    return result.stdout.strip()


def process_directory(directory: Path) -> None:
    """Process all images in the directory."""
    image_files = [
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not image_files:
        print(f"No image files found in {directory}")
        return

    print(f"Found {len(image_files)} image(s) in {directory}")

    for image_path in sorted(image_files):
        txt_path = image_path.with_suffix('.txt')

        if txt_path.exists():
            print(f"Skipping {image_path.name} - caption already exists")
            continue

        print(f"Processing {image_path.name}...")

        try:
            caption = generate_caption(image_path)
            txt_path.write_text(caption, encoding='utf-8')
            print(f"  Created {txt_path.name}")
        except Exception as e:
            print(f"  Error processing {image_path.name}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Generate Instagram captions for images using AI CLI'
    )
    parser.add_argument(
        'directory',
        type=Path,
        help='Directory containing images to process'
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a valid directory", file=sys.stderr)
        sys.exit(1)

    process_directory(args.directory)


if __name__ == '__main__':
    main()
