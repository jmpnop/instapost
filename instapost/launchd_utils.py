"""Utilities for managing InstaPost daemons via macOS launchd."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from instapost.utils import PROJECT_ROOT


# Launchd service labels
SERVICES = {
    "scheduler": "com.instapost.scheduler",
    "watcher": "com.instapost.watcher",
    "mover": "com.instapost.mover",
}

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_SOURCE_DIR = PROJECT_ROOT / "launchd"


def is_launchd_installed() -> bool:
    """Check if launchd plist files are installed."""
    for service_label in SERVICES.values():
        plist_path = LAUNCH_AGENTS_DIR / f"{service_label}.plist"
        if not plist_path.exists():
            return False
    return True


def install_launchd() -> Tuple[bool, str]:
    """
    Install launchd plist files to ~/Library/LaunchAgents/.

    Returns:
        (success, message)
    """
    try:
        # Ensure LaunchAgents directory exists
        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

        # Copy plist files
        installed = []
        for service_name, service_label in SERVICES.items():
            source = PLIST_SOURCE_DIR / f"{service_label}.plist"
            dest = LAUNCH_AGENTS_DIR / f"{service_label}.plist"

            if not source.exists():
                return False, f"Source plist not found: {source}"

            shutil.copy2(source, dest)
            # Set correct permissions (644)
            os.chmod(dest, 0o644)
            installed.append(service_name)

        return True, f"Installed launchd services: {', '.join(installed)}"

    except Exception as e:
        return False, f"Failed to install launchd services: {e}"


def uninstall_launchd() -> Tuple[bool, str]:
    """
    Uninstall launchd plist files from ~/Library/LaunchAgents/.

    Unloads services first, then removes plist files.

    Returns:
        (success, message)
    """
    try:
        # Unload all services first
        for service_label in SERVICES.values():
            try:
                subprocess.run(
                    ["launchctl", "unload", str(LAUNCH_AGENTS_DIR / f"{service_label}.plist")],
                    capture_output=True,
                    check=False
                )
            except Exception:
                pass  # Ignore errors - service might not be loaded

        # Remove plist files
        removed = []
        for service_name, service_label in SERVICES.items():
            plist_path = LAUNCH_AGENTS_DIR / f"{service_label}.plist"
            if plist_path.exists():
                plist_path.unlink()
                removed.append(service_name)

        if removed:
            return True, f"Uninstalled launchd services: {', '.join(removed)}"
        else:
            return True, "No launchd services were installed"

    except Exception as e:
        return False, f"Failed to uninstall launchd services: {e}"


def load_service(service_name: str) -> Tuple[bool, str]:
    """
    Load a launchd service (makes it available to start).

    Returns:
        (success, message)
    """
    service_label = SERVICES.get(service_name)
    if not service_label:
        return False, f"Unknown service: {service_name}"

    plist_path = LAUNCH_AGENTS_DIR / f"{service_label}.plist"
    if not plist_path.exists():
        return False, f"Service not installed: {service_name} (run 'install-launchd' first)"

    try:
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return True, f"Loaded {service_name}"
        else:
            # Check if already loaded
            if "already loaded" in result.stderr.lower():
                return True, f"{service_name} already loaded"
            return False, f"Failed to load {service_name}: {result.stderr}"
    except Exception as e:
        return False, f"Error loading {service_name}: {e}"


def unload_service(service_name: str) -> Tuple[bool, str]:
    """
    Unload a launchd service (stops it and removes from launchd).

    Returns:
        (success, message)
    """
    service_label = SERVICES.get(service_name)
    if not service_label:
        return False, f"Unknown service: {service_name}"

    plist_path = LAUNCH_AGENTS_DIR / f"{service_label}.plist"

    try:
        result = subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return True, f"Unloaded {service_name}"
        else:
            # Check if not loaded
            if "could not find" in result.stderr.lower():
                return True, f"{service_name} not loaded"
            return False, f"Failed to unload {service_name}: {result.stderr}"
    except Exception as e:
        return False, f"Error unloading {service_name}: {e}"


def start_service(service_name: str) -> Tuple[bool, str]:
    """
    Start a launchd service.

    Returns:
        (success, message)
    """
    service_label = SERVICES.get(service_name)
    if not service_label:
        return False, f"Unknown service: {service_name}"

    try:
        result = subprocess.run(
            ["launchctl", "start", service_label],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return True, f"Started {service_name}"
        else:
            return False, f"Failed to start {service_name}: {result.stderr}"
    except Exception as e:
        return False, f"Error starting {service_name}: {e}"


def stop_service(service_name: str) -> Tuple[bool, str]:
    """
    Stop a launchd service.

    Returns:
        (success, message)
    """
    service_label = SERVICES.get(service_name)
    if not service_label:
        return False, f"Unknown service: {service_name}"

    try:
        result = subprocess.run(
            ["launchctl", "stop", service_label],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return True, f"Stopped {service_name}"
        else:
            return False, f"Failed to stop {service_name}: {result.stderr}"
    except Exception as e:
        return False, f"Error stopping {service_name}: {e}"


def get_service_status(service_name: str) -> Dict[str, any]:
    """
    Get status of a launchd service.

    Returns:
        dict with keys: loaded, running, pid, status
    """
    service_label = SERVICES.get(service_name)
    if not service_label:
        return {"loaded": False, "running": False, "pid": None, "status": "unknown service"}

    try:
        # Check if service is loaded and get its status
        # Use 'launchctl list' without specific label to get all services
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return {"loaded": False, "running": False, "pid": None, "status": "error querying launchctl"}

        # Parse output - look for our service
        # Format: "PID    Status    Label"
        # Example: "70070	0	com.instapost.scheduler"
        # or:      "-      0       com.instapost.scheduler" (loaded but not running)
        for line in result.stdout.strip().split('\n'):
            if service_label in line:
                parts = line.split()
                if len(parts) < 3:
                    continue

                pid_str = parts[0]
                if pid_str == "-":
                    # Loaded but not running
                    return {"loaded": True, "running": False, "pid": None, "status": "loaded but not running"}
                else:
                    # Running
                    try:
                        pid = int(pid_str)
                        return {"loaded": True, "running": True, "pid": pid, "status": "running"}
                    except ValueError:
                        return {"loaded": True, "running": False, "pid": None, "status": "unknown"}

        # Service not found in list - not loaded
        return {"loaded": False, "running": False, "pid": None, "status": "not loaded"}

    except Exception as e:
        return {"loaded": False, "running": False, "pid": None, "status": f"error: {e}"}


def get_all_service_statuses() -> Dict[str, Dict[str, any]]:
    """Get status of all InstaPost services."""
    return {name: get_service_status(name) for name in SERVICES.keys()}
