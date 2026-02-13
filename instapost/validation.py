"""Image validation utilities for Instagram requirements."""

import logging
from pathlib import Path
from PIL import Image
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Instagram image requirements
# https://developers.facebook.com/docs/instagram-api/reference/ig-user/media
MIN_WIDTH = 320
MIN_HEIGHT = 320
# Note: Instagram accepts larger images and will resize them
# 1440px is recommended for best quality, but not a hard limit
# We'll only enforce minimum size and aspect ratio
MAX_FILE_SIZE_MB = 8
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Aspect ratio requirements (strictly enforced by Instagram)
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

            # Check minimum dimensions
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                return False, f"Image too small: {width}x{height} (min {MIN_WIDTH}x{MIN_HEIGHT})"

            # Note: No maximum dimension check - Instagram accepts large images and resizes them
            # 1440px is recommended for optimal quality but not enforced

            # Check aspect ratio (strictly enforced by Instagram)
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


def auto_fix_image(image_path: str | Path) -> Tuple[bool, str]:
    """Automatically fix image to meet Instagram requirements.

    Fixes applied:
    - Crops to valid aspect ratio (0.8 to 1.91) if needed
    - Resizes if file size > 8MB
    - Maintains best quality possible

    Args:
        image_path: Path to the image file

    Returns:
        Tuple of (was_modified, message)
        - (True, "description of fixes") if image was modified
        - (False, "Image already valid") if no fixes needed

    Raises:
        ImageValidationError: If image cannot be fixed
    """
    path = Path(image_path)

    if not path.exists():
        raise ImageValidationError(f"File not found: {path}")

    try:
        img = Image.open(path)
        original_size = img.size
        original_format = img.format
        modified = False
        fixes = []

        width, height = img.size
        aspect_ratio = width / height

        # Fix 1: Aspect ratio correction
        if aspect_ratio < MIN_ASPECT_RATIO or aspect_ratio > MAX_ASPECT_RATIO:
            logger.info(f"Auto-fixing aspect ratio: {aspect_ratio:.3f} -> valid range")

            if aspect_ratio < MIN_ASPECT_RATIO:
                # Too portrait - crop height from center
                target_aspect = MIN_ASPECT_RATIO
                new_height = int(width / target_aspect)

                if new_height < height:
                    # Crop vertically from center
                    top_crop = (height - new_height) // 2
                    bottom_crop = top_crop + new_height
                    img = img.crop((0, top_crop, width, bottom_crop))
                    fixes.append(f"Cropped height {height}→{new_height} (aspect {aspect_ratio:.3f}→{target_aspect:.3f})")
                    modified = True

            elif aspect_ratio > MAX_ASPECT_RATIO:
                # Too landscape - crop width from center
                target_aspect = MAX_ASPECT_RATIO
                new_width = int(height * target_aspect)

                if new_width < width:
                    # Crop horizontally from center
                    left_crop = (width - new_width) // 2
                    right_crop = left_crop + new_width
                    img = img.crop((left_crop, 0, right_crop, height))
                    fixes.append(f"Cropped width {width}→{new_width} (aspect {aspect_ratio:.3f}→{target_aspect:.3f})")
                    modified = True

        # Fix 2: File size reduction (if needed after crop, or if original was too large)
        if modified:
            # Save to temp to check size after crop
            temp_path = path.with_suffix('.tmp' + path.suffix)
            img.save(temp_path, format=original_format, quality=95, optimize=True)
            temp_size = temp_path.stat().st_size

            if temp_size > MAX_FILE_SIZE_BYTES:
                # Need to resize
                size_mb = temp_size / (1024 * 1024)
                logger.info(f"Image still too large after crop: {size_mb:.2f}MB, resizing...")

                # Calculate scale factor to get under 8MB (aim for 7MB to be safe)
                target_bytes = 7 * 1024 * 1024
                scale = (target_bytes / temp_size) ** 0.5  # Square root because area scales with dimension squared

                new_width = int(img.width * scale)
                new_height = int(img.height * scale)

                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                fixes.append(f"Resized to {new_width}x{new_height} to reduce file size")

            temp_path.unlink(missing_ok=True)
        else:
            # Check original file size
            file_size = path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                size_mb = file_size / (1024 * 1024)
                logger.info(f"Image too large: {size_mb:.2f}MB, resizing...")

                # Calculate scale factor
                target_bytes = 7 * 1024 * 1024
                scale = (target_bytes / file_size) ** 0.5

                new_width = int(width * scale)
                new_height = int(height * scale)

                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                fixes.append(f"Resized {width}x{height}→{new_width}x{new_height} to reduce file size")
                modified = True

        # Save the fixed image
        if modified:
            # Save fixed image directly (overwrite original)
            img.save(path, format=original_format, quality=95, optimize=True)

            # Verify the fix
            is_valid, error = validate_image_file(path)
            if not is_valid:
                raise ImageValidationError(f"Auto-fix failed: {error}")

            final_size = path.stat().st_size
            final_mb = final_size / (1024 * 1024)
            message = f"Auto-fixed image: {', '.join(fixes)}. Final: {img.size[0]}x{img.size[1]}, {final_mb:.2f}MB"
            logger.info(message)
            return True, message
        else:
            return False, "Image already valid - no fixes needed"

    except Exception as e:
        raise ImageValidationError(f"Failed to auto-fix image: {str(e)}")


def validate_and_fix(image_path: str | Path, auto_fix: bool = True) -> Tuple[bool, Optional[str]]:
    """Validate image and optionally auto-fix if invalid.

    Args:
        image_path: Path to the image file
        auto_fix: If True, attempt to auto-fix invalid images

    Returns:
        Tuple of (is_valid, message)
        - (True, None) if valid or successfully fixed
        - (False, error_message) if invalid and cannot be fixed
    """
    # First check if valid
    is_valid, error = validate_image_file(image_path)

    if is_valid:
        return True, None

    if not auto_fix:
        return False, error

    # Try to auto-fix
    try:
        was_modified, fix_message = auto_fix_image(image_path)
        if was_modified:
            return True, f"Auto-fixed: {fix_message}"
        return True, None
    except ImageValidationError as e:
        return False, f"Cannot auto-fix: {str(e)}"
