"""Remote execution utilities for running commands on the VM."""

import os
import subprocess
from typing import Optional, Tuple

from dotenv import load_dotenv


def get_vm_config() -> dict:
    """Get VM configuration from environment."""
    load_dotenv()
    return {
        'host': os.getenv('VM_HOST', 'instapost-deploy'),
        'instapost_dir': os.getenv('VM_INSTAPOST_DIR', '/home/ironsirens/instapost'),
        'images_dir': os.getenv('VM_IMAGES_DIR', '/mnt/s3/images'),
        'processed_dir': os.getenv('VM_PROCESSED_DIR', '/mnt/s3/processed'),
    }


def ssh(command: str, capture: bool = True, timeout: int = 30) -> Tuple[bool, str]:
    """Execute a command on the remote VM via SSH.

    Args:
        command: Shell command to execute
        capture: Whether to capture output (False for interactive)
        timeout: Command timeout in seconds

    Returns:
        Tuple of (success, output)
    """
    config = get_vm_config()
    ssh_cmd = ['ssh', config['host'], command]

    try:
        if capture:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output.strip()
        else:
            result = subprocess.run(ssh_cmd, timeout=timeout)
            return result.returncode == 0, ''
    except subprocess.TimeoutExpired:
        return False, f'Command timed out after {timeout}s'
    except Exception as e:
        return False, str(e)


def run_cron_module(module: str, *args) -> Tuple[bool, str]:
    """Run an instapost cron module on the remote VM.

    Args:
        module: Module name (e.g., 'watcher_cron', 'scheduler_cron')
        *args: Additional arguments to pass

    Returns:
        Tuple of (success, output)
    """
    config = get_vm_config()
    cmd = f"cd {config['instapost_dir']} && ~/.local/bin/uv run python -m instapost.cron.{module}"
    if args:
        cmd += ' ' + ' '.join(str(a) for a in args)
    return ssh(cmd, timeout=120)


def read_json(filename: str) -> Tuple[bool, str]:
    """Read a JSON file from the remote VM.

    Args:
        filename: Filename relative to instapost directory

    Returns:
        Tuple of (success, json_content)
    """
    config = get_vm_config()
    return ssh(f"cat {config['instapost_dir']}/{filename} 2>/dev/null || echo '[]'")


def write_json(filename: str, content: str) -> Tuple[bool, str]:
    """Write JSON content to a file on the remote VM.

    Args:
        filename: Filename relative to instapost directory
        content: JSON string to write

    Returns:
        Tuple of (success, output)
    """
    config = get_vm_config()
    # Escape single quotes in content
    escaped = content.replace("'", "'\"'\"'")
    return ssh(f"echo '{escaped}' > {config['instapost_dir']}/{filename}")


def list_images() -> Tuple[bool, str]:
    """List image files in the remote images directory.

    Returns:
        Tuple of (success, newline-separated filenames)
    """
    config = get_vm_config()
    return ssh(f"ls -1 {config['images_dir']}/*.{{jpg,jpeg,png,gif}} 2>/dev/null | xargs -n1 basename 2>/dev/null || true")


def tail_log(log_name: str, lines: int = 50) -> Tuple[bool, str]:
    """Tail a log file on the remote VM.

    Args:
        log_name: Log filename (e.g., 'watcher_cron.log')
        lines: Number of lines to show

    Returns:
        Tuple of (success, log_content)
    """
    config = get_vm_config()
    return ssh(f"tail -n {lines} {config['instapost_dir']}/logs/{log_name} 2>/dev/null || echo 'Log not found'")


def check_cron() -> Tuple[bool, str]:
    """Check if cron jobs are installed on the remote VM.

    Returns:
        Tuple of (success, crontab_content)
    """
    return ssh("crontab -l 2>/dev/null || echo 'No crontab'")


def upload_image(local_path: str) -> Tuple[bool, str]:
    """Upload an image to the remote VM.

    Args:
        local_path: Local path to the image file

    Returns:
        Tuple of (success, remote_path)
    """
    config = get_vm_config()
    remote_path = f"{config['images_dir']}/{os.path.basename(local_path)}"

    try:
        result = subprocess.run(
            ['scp', local_path, f"{config['host']}:{remote_path}"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return True, remote_path
        return False, result.stderr
    except Exception as e:
        return False, str(e)


def disk_usage() -> Tuple[bool, str]:
    """Get disk usage on the remote VM.

    Returns:
        Tuple of (success, df_output)
    """
    config = get_vm_config()
    return ssh(f"df -h {config['images_dir']}")
