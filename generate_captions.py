#!/usr/bin/env python3
"""
Generate Instagram captions for images using Claude CLI.
Usage: python generate_captions.py /path/to/image/directory
"""

import argparse
import subprocess
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

CAPTION_PROMPT = """Read and analyze the image at {image_path} and write the perfect caption using niche language.

NICHE FOR THIS ACCOUNT: Female Rider | Member of Women Motorcycle Club | Riding Lifestyle (USA) – New York, Boston and Florida.

Key focus: not a model, not a 'girl with a bike', but a MEMBER.

Rule: In addition to describing what is in the photo (context), each photo post must contain 1 key phrase/algorithmic anchor from the list of 15 anchors.

Core keywords (algorithmic anchors):
1. women motorcycle club
2. ladies riding club
3. female bikers
4. women who ride
5. motorcycle sisterhood
6. women riders community
7. biker women lifestyle
8. ladies motorcycle life
9. women on motorcycles
10. female motorcycle riders
11. riding club women
12. women biker culture
13. women empowerment riding
14. ladies RC
15. women-led motorcycle club

Additionally, you can use (meaningfully use) HIDDEN LSI KEYS in the context of the photo.

LSI signals:
1. club patch
2. road discipline
3. formation ride
4. earned respect
5. club rules
6. long ride day
7. riding responsibility
8. not a photo op
9. part of the chapter
10. ride speaks louder

Write ONLY the caption, no explanations or metadata.

Should be in less than four sentences.
"""


def generate_caption(image_path: Path) -> str:
    """Generate a caption for the given image using Claude CLI."""
    prompt = CAPTION_PROMPT.format(image_path=image_path.resolve())

    result = subprocess.run(
        ['claude', '-p', prompt],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

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
        description='Generate Instagram captions for images using Claude CLI'
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
