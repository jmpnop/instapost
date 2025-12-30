"""Image validation utilities for Instagram requirements."""

from pathlib import Path
from PIL import Image
from typing import Tuple, Optional

# Instagram image requirements
# https://developers.facebook.com/docs/instagram-api/reference/ig-user/media
MIN_WIDTH = 320
MIN_HEIGHT = 320
MAX_WIDTH = 1440
MAX_HEIGHT = 1440
MAX_FILE_SIZE_MB = 8
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Aspect ratio requirements
MIN_ASPECT_RATIO = 0.8  # 4:5 portrait
MAX_ASPECT_RATIO = 1.91  # 1.91:1 landscape


class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass


def validate_image_file(image_path: str | Path) -> Tuple[bool, Optional[str]]:
    """Validate image against Instagram requirements.

    Args:
        image_path: Path to the image file

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
    """
    path = Path(image_path)

    # Check file exists
    if not path.exists():
        return False, f"File not found: {path}"

    # Check file size
    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        return False, f"File too large: {size_mb:.2f}MB (max {MAX_FILE_SIZE_MB}MB)"

    # Check if it's a valid image
    try:
        with Image.open(path) as img:
            width, height = img.size

            # Check dimensions
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                return False, f"Image too small: {width}x{height} (min {MIN_WIDTH}x{MIN_HEIGHT})"

            # Instagram recommends max 1440px on longest side
            if width > MAX_WIDTH or height > MAX_HEIGHT:
                return False, f"Image too large: {width}x{height} (max {MAX_WIDTH}x{MAX_HEIGHT})"

            # Check aspect ratio
            aspect_ratio = width / height
            if aspect_ratio < MIN_ASPECT_RATIO:
                return False, f"Aspect ratio too portrait: {aspect_ratio:.2f} (min {MIN_ASPECT_RATIO})"

            if aspect_ratio > MAX_ASPECT_RATIO:
                return False, f"Aspect ratio too landscape: {aspect_ratio:.2f} (max {MAX_ASPECT_RATIO})"

            # Check format
            if img.format not in ['JPEG', 'PNG']:
                return False, f"Unsupported format: {img.format} (use JPEG or PNG)"

            return True, None

    except Exception as e:
        return False, f"Invalid image file: {str(e)}"


def get_image_info(image_path: str | Path) -> dict:
    """Get detailed image information.

    Args:
        image_path: Path to the image file

    Returns:
        Dictionary with image information
    """
    path = Path(image_path)

    info = {
        'path': str(path),
        'exists': path.exists(),
        'size_bytes': 0,
        'size_mb': 0.0,
        'width': 0,
        'height': 0,
        'aspect_ratio': 0.0,
        'format': None,
        'valid': False,
        'error': None
    }

    if not path.exists():
        info['error'] = "File not found"
        return info

    info['size_bytes'] = path.stat().st_size
    info['size_mb'] = info['size_bytes'] / (1024 * 1024)

    try:
        with Image.open(path) as img:
            info['width'] = img.width
            info['height'] = img.height
            info['aspect_ratio'] = img.width / img.height
            info['format'] = img.format

        is_valid, error = validate_image_file(path)
        info['valid'] = is_valid
        info['error'] = error

    except Exception as e:
        info['error'] = str(e)

    return info


def validate_and_raise(image_path: str | Path) -> None:
    """Validate image and raise ImageValidationError if invalid.

    Args:
        image_path: Path to the image file

    Raises:
        ImageValidationError: If image validation fails
    """
    is_valid, error = validate_image_file(image_path)
    if not is_valid:
        raise ImageValidationError(error)
