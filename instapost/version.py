"""Version information for InstaPost."""

__version__ = "0.1.0"
__build__ = "2026-01-11"

def get_version_string():
    """Get formatted version string for logging."""
    return f"InstaPost v{__version__} (build {__build__})"
