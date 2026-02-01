"""Static hosting client for self-hosted images via Angie + Cloudflare tunnel."""

import os
from urllib.parse import quote


def get_base_url() -> str:
    """Get the base URL for self-hosted images."""
    return os.getenv("IMAGE_BASE_URL", "https://instapost.celestialtech.io")


def get_public_url(filename: str) -> str:
    """Return the public URL for an image file.

    Args:
        filename: Name of the image file

    Returns:
        Public URL accessible via Cloudflare tunnel
    """
    base_url = get_base_url()
    # URL-encode the filename to handle special characters
    encoded_filename = quote(filename, safe='')
    return f"{base_url}/{encoded_filename}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print(get_public_url(filename))
    else:
        print(f"Base URL: {get_base_url()}")
