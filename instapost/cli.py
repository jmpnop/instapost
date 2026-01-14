"""Command-line interface for instapost."""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional

import click

from instapost.config import load_settings
from instapost.clients.dropbox import DropboxClient
from instapost.clients.instagram import InstagramClient
from instapost.utils import PROJECT_ROOT
from instapost.schedule_utils import remove_from_schedule, update_schedule_entry, ScheduleValidationError
from instapost.version import __version__, __build__


@click.group()
@click.option(
    "--env-file",
    "-e",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    help="Path to .env file with API credentials.",
)
@click.pass_context
def cli(ctx: click.Context, env_file: Optional[str] = None):
    """Post images to Instagram using Facebook Graph API and Dropbox."""
    try:
        # Load settings from .env file
        settings = load_settings(env_file)
        
        # Initialize clients
        dropbox_client = DropboxClient(settings.dropbox)
        instagram_client = InstagramClient(settings.instagram)
        
        # Store clients in context
        ctx.obj = {
            "settings": settings,
            "dropbox_client": dropbox_client,
            "instagram_client": instagram_client,
        }
    except Exception as e:
        click.echo(f"Error initializing clients: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("image_path", type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True))
@click.option("--caption", "-c", required=True, help="Caption for the Instagram post.")
@click.option("--location-id", "-l", help="Instagram location ID (optional).")
@click.pass_context
def post(ctx: click.Context, image_path: str, caption: str, location_id: Optional[str] = None):
    """Upload image to Dropbox and post it to Instagram.
    
    IMAGE_PATH is the path to the image file to upload.
    """
    dropbox_client = ctx.obj["dropbox_client"]
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Upload image to Dropbox and get shared link
        click.echo("Uploading image to Dropbox...")
        image_url = dropbox_client.upload_and_get_link(image_path)
        click.echo(f"Image uploaded: {image_url}")
        
        # Post image to Instagram
        click.echo("Posting image to Instagram...")
        response = instagram_client.post_image(image_url, caption, location_id)
        click.echo(f"Image posted to Instagram. Post ID: {response.get('id')}")
    except Exception as e:
        click.echo(f"Error posting image: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def info(ctx: click.Context):
    """Get information about the Instagram business account."""
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Get account information
        info = instagram_client.get_account_info()
        
        # Display account information
        click.echo("Instagram Account Information:")
        click.echo(f"Name: {info.get('name')}")
        click.echo(f"Username: {info.get('username')}")
        click.echo(f"Followers: {info.get('followers_count')}")
        click.echo(f"Media Count: {info.get('media_count')}")
    except Exception as e:
        click.echo(f"Error getting account information: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--limit", "-n", type=int, default=5, help="Number of recent media items to display.")
@click.pass_context
def media(ctx: click.Context, limit: int):
    """Get recent media from the Instagram business account."""
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Get recent media
        media = instagram_client.get_media(limit)
        
        # Display recent media
        click.echo(f"Recent Instagram Media (up to {limit} items):")
        for item in media.get("data", []):
            click.echo(f"ID: {item.get('id')}")
            click.echo(f"Type: {item.get('media_type')}")
            click.echo(f"Caption: {item.get('caption', 'No caption')[:50]}...")
            click.echo(f"URL: {item.get('permalink')}")
            click.echo("---")
    except Exception as e:
        click.echo(f"Error getting recent media: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def token_info(ctx: click.Context):
    """Check Facebook token validity, expiration, and properties."""
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Get token information
        token_info = instagram_client.get_token_info()
        
        # Display token information
        click.echo("Facebook Access Token Information:")
        click.echo(f"Valid: {token_info.get('is_valid', False)}")
        
        # Display expiration date if available
        expires_at = token_info.get('expires_at')
        if expires_at:
            click.echo(f"Expires At: {expires_at}")
        else:
            click.echo("Expires At: Never (long-lived token)")
        
        # Display scopes
        scopes = token_info.get('scopes', [])
        if scopes:
            click.echo("Scopes:")
            for scope in scopes:
                click.echo(f"  - {scope}")
        else:
            click.echo("Scopes: None or not available")
        
        # Display user ID and app ID
        click.echo(f"User ID: {token_info.get('user_id', 'Not available')}")
        click.echo(f"App ID: {token_info.get('app_id', 'Not available')}")
        click.echo(f"Token Type: {token_info.get('token_type', 'Not available')}")
    except Exception as e:
        click.echo(f"Error checking token information: {e}", err=True)
        sys.exit(1)


@cli.command()
def dropbox():
    """Set up Dropbox authentication and get refresh token."""
    try:
        # Generate authentication flow
        auth_url, auth_flow = DropboxClient.generate_auth_flow()

        # Display instructions
        click.echo("1. Go to the following URL in your browser:")
        click.echo(auth_url)
        click.echo("2. Click 'Allow' (you might need to log in first).")
        click.echo("3. Copy the authorization code.")

        # Get authorization code
        auth_code = click.prompt("Enter the authorization code")

        # Complete authentication flow
        refresh_token = DropboxClient.complete_auth_flow(auth_flow, auth_code)

        # Display refresh token
        click.echo("\nDropbox authentication successful!")
        click.echo(f"Refresh Token: {refresh_token}")
        click.echo("\nAdd this token to your .env file as DROPBOX_REFRESH_TOKEN.")
    except Exception as e:
        click.echo(f"Error setting up Dropbox authentication: {e}", err=True)
        sys.exit(1)


def _get_daemon_pids():
    """Get PIDs of running InstaPost daemons."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "instapost.daemons"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return [int(pid) for pid in result.stdout.strip().split('\n')]
        return []
    except Exception:
        return []


def _get_daemon_info(pid):
    """Get daemon name from PID."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            cmd = result.stdout.strip()
            if "watcher" in cmd:
                return "watcher"
            elif "scheduler" in cmd:
                return "scheduler"
            elif "mover" in cmd:
                return "mover"
        return "unknown"
    except Exception:
        return "unknown"


def _get_process_runtime(pid):
    """Get process runtime."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etime="],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "?"
    except Exception:
        return "?"


@cli.command()
def start():
    """Start all InstaPost daemons (watcher, scheduler, mover)."""
    click.echo("Starting InstaPost daemons...")
    click.echo("=" * 40)

    # Check if any daemons are already running
    pids = _get_daemon_pids()
    if pids:
        click.echo("Warning: Some InstaPost daemons are already running")
        click.echo("Run 'instapost stop' first to stop them")
        sys.exit(1)

    # Ensure directories exist
    os.makedirs(PROJECT_ROOT / "logs", exist_ok=True)
    os.makedirs(PROJECT_ROOT / "images", exist_ok=True)
    os.makedirs(PROJECT_ROOT / "processed", exist_ok=True)

    # Start watcher
    click.echo("Starting watcher daemon...")
    with open(PROJECT_ROOT / "logs" / "watcher.log", "a") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "instapost.daemons.watcher", "./images"],
            stdout=log,
            stderr=log,
            cwd=PROJECT_ROOT,
            start_new_session=True
        )
    click.echo(f"  Watcher started (PID: {proc.pid})")
    time.sleep(1)

    # Start scheduler
    click.echo("Starting scheduler daemon...")
    with open(PROJECT_ROOT / "logs" / "scheduler.log", "a") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "instapost.daemons.scheduler"],
            stdout=log,
            stderr=log,
            cwd=PROJECT_ROOT,
            start_new_session=True
        )
    click.echo(f"  Scheduler started (PID: {proc.pid})")
    time.sleep(1)

    # Start mover
    click.echo("Starting mover daemon...")
    with open(PROJECT_ROOT / "logs" / "mover.log", "a") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "instapost.daemons.mover", "./images", "./processed"],
            stdout=log,
            stderr=log,
            cwd=PROJECT_ROOT,
            start_new_session=True
        )
    click.echo(f"  Mover started (PID: {proc.pid})")

    click.echo()
    click.echo("=" * 40)
    click.echo("All daemons started successfully!")
    click.echo()
    click.echo("Monitor logs with:")
    click.echo("  tail -f logs/watcher.log")
    click.echo("  tail -f logs/scheduler.log")
    click.echo("  tail -f logs/mover.log")
    click.echo()
    click.echo("Check status with: instapost status")
    click.echo("Stop daemons with: instapost stop")


@cli.command()
def stop():
    """Stop all InstaPost daemons."""
    click.echo("Stopping InstaPost daemons...")
    click.echo("=" * 40)

    # Get all daemon PIDs
    pids = _get_daemon_pids()

    if not pids:
        click.echo("No InstaPost daemons are currently running")
        return

    click.echo(f"Found {len(pids)} daemon(s) running")
    click.echo()

    # Stop each daemon
    for pid in pids:
        daemon_name = _get_daemon_info(pid)
        click.echo(f"Stopping {daemon_name} (PID: {pid})...")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            click.echo(f"  Already stopped")
        except Exception as e:
            click.echo(f"  Error: {e}")

    # Wait for graceful shutdown
    time.sleep(2)

    # Check if any processes are still running
    remaining = _get_daemon_pids()

    if remaining:
        click.echo()
        click.echo("Some processes didn't stop gracefully. Force killing...")
        for pid in remaining:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        time.sleep(1)

    # Final check
    final_check = _get_daemon_pids()

    if final_check:
        click.echo()
        click.echo("Error: Some daemons are still running")
        click.echo(f"PIDs: {final_check}")
        sys.exit(1)

    click.echo()
    click.echo("=" * 40)
    click.echo("All daemons stopped successfully!")


@cli.command()
def status():
    """Check status of InstaPost daemons."""
    import json

    click.echo("InstaPost Daemon Status")
    click.echo("=" * 40)
    click.echo()

    # Get all daemon PIDs
    pids = _get_daemon_pids()

    # Track which daemons are running
    running_daemons = {}
    for pid in pids:
        daemon_name = _get_daemon_info(pid)
        runtime = _get_process_runtime(pid)
        running_daemons[daemon_name] = (pid, runtime)

    # Check each expected daemon
    for daemon_name in ["watcher", "scheduler", "mover"]:
        if daemon_name in running_daemons:
            pid, runtime = running_daemons[daemon_name]
            click.echo(f"✅ {daemon_name.capitalize():10s}: Running (PID: {pid}, Runtime: {runtime})")
        else:
            click.echo(f"❌ {daemon_name.capitalize():10s}: Not running")

    click.echo()
    click.echo("=" * 40)

    # Show version info
    click.echo(f"Version: v{__version__} (build {__build__})")

    # Show schedule info if files exist
    schedule_file = PROJECT_ROOT / "schedule.json"
    processed_file = PROJECT_ROOT / "processed.json"

    if schedule_file.exists():
        try:
            with open(schedule_file) as f:
                scheduled = len(json.load(f))
            click.echo(f"Scheduled posts: {scheduled}")
        except Exception:
            pass

    if processed_file.exists():
        try:
            with open(processed_file) as f:
                processed = len(json.load(f))
            click.echo(f"Processed posts: {processed}")
        except Exception:
            pass

    # Show TEST_MODE status
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            with open(env_file) as f:
                for line in f:
                    if line.startswith("TEST_MODE="):
                        test_mode = line.split("=", 1)[1].strip()
                        if test_mode.lower() in ["true", "1", "yes"]:
                            click.echo("Mode: TEST MODE (immediate posting)")
                        else:
                            click.echo("Mode: PRODUCTION (scheduled posting)")
                        break
        except Exception:
            pass

    click.echo()

    # Overall status
    all_running = all(d in running_daemons for d in ["watcher", "scheduler", "mover"])
    none_running = not any(d in running_daemons for d in ["watcher", "scheduler", "mover"])

    if all_running:
        click.echo("Status: All systems operational ✅")
    elif none_running:
        click.echo("Status: All systems stopped ❌")
        click.echo("Run 'instapost start' to start daemons")
    else:
        click.echo("Status: Partial failure ⚠️")
        click.echo("Some daemons are not running. Run 'instapost restart' to restart all.")


@cli.command()
def restart():
    """Restart all InstaPost daemons."""
    click.echo("Restarting InstaPost daemons...")
    click.echo()

    # Stop daemons
    ctx = click.get_current_context()
    ctx.invoke(stop)

    click.echo()
    time.sleep(1)

    # Start daemons
    ctx.invoke(start)


@cli.command()
def queue():
    """View scheduled posts in the queue."""
    import json
    from datetime import datetime

    schedule_file = PROJECT_ROOT / "schedule.json"

    if not schedule_file.exists():
        click.echo("No schedule file found")
        return

    try:
        with open(schedule_file) as f:
            scheduled = json.load(f)

        if not scheduled:
            click.echo("No posts currently scheduled")
            return

        click.echo("Scheduled Posts Queue")
        click.echo("=" * 60)
        click.echo()

        now = datetime.now()
        for i, entry in enumerate(scheduled, 1):
            filename = entry.get('filename', 'Unknown')
            scheduled_time = entry.get('time', 'Unknown')

            # Parse and format time
            try:
                dt = datetime.fromisoformat(scheduled_time)
                time_str = dt.strftime('%a %b %d, %Y at %H:%M:%S %Z')

                # Calculate time until post
                time_diff = dt.replace(tzinfo=None) - now
                if time_diff.total_seconds() > 0:
                    days = time_diff.days
                    hours, remainder = divmod(time_diff.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)

                    if days > 0:
                        countdown = f"in {days}d {hours}h {minutes}m"
                    elif hours > 0:
                        countdown = f"in {hours}h {minutes}m"
                    else:
                        countdown = f"in {minutes}m"
                else:
                    countdown = "overdue"

                time_str += f" ({countdown})"
            except Exception:
                time_str = scheduled_time

            click.echo(f"{i}. {filename}")
            click.echo(f"   Scheduled: {time_str}")
            click.echo()

    except Exception as e:
        click.echo(f"Error reading schedule: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('filename')
def cancel(filename):
    """Cancel a scheduled post and remove it from the queue.

    FILENAME is the name of the image file to cancel.
    """
    import json

    try:
        remove_from_schedule(filename)
        click.echo(f"✅ Cancelled: {filename}")

        # Show remaining queue
        schedule_file = PROJECT_ROOT / "schedule.json"
        if schedule_file.exists():
            with open(schedule_file) as f:
                remaining = len(json.load(f))
            click.echo(f"Remaining posts in queue: {remaining}")

    except ScheduleValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error canceling post: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('filename')
@click.argument('new_time')
def reschedule(filename, new_time):
    """Reschedule a post to a different time.

    FILENAME is the name of the image file to reschedule.
    NEW_TIME is the new time in ISO format (YYYY-MM-DDTHH:MM:SS).

    Example: instapost reschedule image.jpg 2025-12-30T10:00:00
    """
    import json
    from datetime import datetime

    # Validate new time format
    try:
        datetime.fromisoformat(new_time)
    except ValueError:
        click.echo(f"Error: Invalid time format. Use ISO format: YYYY-MM-DDTHH:MM:SS", err=True)
        sys.exit(1)

    try:
        # Get old time before update
        schedule_file = PROJECT_ROOT / "schedule.json"
        old_time = None
        if schedule_file.exists():
            with open(schedule_file) as f:
                for entry in json.load(f):
                    if entry.get('filename') == filename:
                        old_time = entry.get('time')
                        break

        # Update with validation
        update_schedule_entry(filename, new_time=new_time)

        click.echo(f"✅ Rescheduled: {filename}")
        if old_time:
            click.echo(f"   Old time: {old_time}")
        click.echo(f"   New time: {new_time}")

    except ScheduleValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error rescheduling post: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--daemon', '-d', type=click.Choice(['watcher', 'scheduler', 'mover', 'all']), default='all',
              help='Which daemon logs to view (default: all)')
@click.option('--lines', '-n', type=int, default=50, help='Number of lines to show (default: 50)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output (like tail -f)')
def logs(daemon, lines, follow):
    """View daemon logs.

    Examples:
        instapost logs                    # Show last 50 lines of all logs
        instapost logs -d scheduler -n 100  # Show last 100 lines of scheduler
        instapost logs -f                  # Follow all logs in real-time
    """
    log_dir = PROJECT_ROOT / "logs"

    if not log_dir.exists():
        click.echo("No logs directory found")
        return

    daemon_logs = {
        'watcher': log_dir / 'watcher.log',
        'scheduler': log_dir / 'scheduler.log',
        'mover': log_dir / 'mover.log'
    }

    # Determine which logs to show
    if daemon == 'all':
        logs_to_show = daemon_logs
    else:
        logs_to_show = {daemon: daemon_logs[daemon]}

    if follow:
        # Use tail -f for following
        log_files = [str(log) for log in logs_to_show.values() if log.exists()]
        if not log_files:
            click.echo("No log files found")
            return

        try:
            subprocess.run(['tail', '-f'] + log_files)
        except KeyboardInterrupt:
            click.echo("\nStopped following logs")
    else:
        # Show last N lines
        for daemon_name, log_file in logs_to_show.items():
            if not log_file.exists():
                click.echo(f"No log file for {daemon_name}")
                continue

            click.echo(f"{'=' * 60}")
            click.echo(f"{daemon_name.upper()} LOG (last {lines} lines)")
            click.echo(f"{'=' * 60}")

            try:
                result = subprocess.run(
                    ['tail', '-n', str(lines), str(log_file)],
                    capture_output=True,
                    text=True
                )
                click.echo(result.stdout)
            except Exception as e:
                click.echo(f"Error reading log: {e}", err=True)

            if len(logs_to_show) > 1:
                click.echo()


@cli.command()
@click.option('--limit', '-n', type=int, default=10, help='Number of posts to show (default: 10)')
def history(limit):
    """View post history with URLs and timestamps."""
    import json
    from datetime import datetime

    processed_file = PROJECT_ROOT / "processed.json"

    if not processed_file.exists():
        click.echo("No processed posts found")
        return

    try:
        with open(processed_file) as f:
            processed = json.load(f)

        if not processed:
            click.echo("No posts have been processed yet")
            return

        # Show most recent first
        processed = list(reversed(processed[-limit:]))

        click.echo(f"Post History (last {min(limit, len(processed))} posts)")
        click.echo("=" * 60)
        click.echo()

        for i, entry in enumerate(processed, 1):
            filename = entry.get('filename', 'Unknown')
            url = entry.get('url', 'No URL')
            timestamp = entry.get('timestamp', '')

            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime('%a %b %d, %Y at %H:%M:%S')
            except Exception:
                time_str = timestamp

            click.echo(f"{i}. {filename}")
            click.echo(f"   Posted: {time_str}")
            click.echo(f"   URL: {url}")
            click.echo()

    except Exception as e:
        click.echo(f"Error reading history: {e}", err=True)
        sys.exit(1)


@cli.command()
def health():
    """Check system health (daemons, schedule, disk space, connectivity)."""
    import json

    click.echo("InstaPost Health Check")
    click.echo("=" * 60)
    click.echo()

    issues = []
    warnings = []

    # Check daemons
    pids = _get_daemon_pids()
    running_daemons = {_get_daemon_info(pid) for pid in pids}

    for daemon_name in ["watcher", "scheduler", "mover"]:
        if daemon_name in running_daemons:
            click.echo(f"✅ {daemon_name.capitalize()} daemon: Running")
        else:
            click.echo(f"❌ {daemon_name.capitalize()} daemon: Not running")
            issues.append(f"{daemon_name} daemon not running")

    click.echo()

    # Check schedule file
    schedule_file = PROJECT_ROOT / "schedule.json"
    if schedule_file.exists():
        try:
            with open(schedule_file) as f:
                scheduled = json.load(f)
            click.echo(f"✅ Schedule file: OK ({len(scheduled)} posts queued)")
        except Exception as e:
            click.echo(f"⚠️  Schedule file: Error reading - {e}")
            warnings.append(f"Schedule file error: {e}")
    else:
        click.echo(f"⚠️  Schedule file: Not found")
        warnings.append("Schedule file missing")

    # Check directories
    for dir_name, dir_path in [("images", PROJECT_ROOT / "images"),
                                ("processed", PROJECT_ROOT / "processed"),
                                ("logs", PROJECT_ROOT / "logs")]:
        if dir_path.exists():
            click.echo(f"✅ {dir_name.capitalize()} directory: Exists")
        else:
            click.echo(f"❌ {dir_name.capitalize()} directory: Missing")
            issues.append(f"{dir_name} directory missing")

    # Check disk space
    try:
        stat = os.statvfs(PROJECT_ROOT)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
        used_percent = ((total_gb - free_gb) / total_gb) * 100

        if free_gb < 1:
            click.echo(f"❌ Disk space: {free_gb:.2f} GB free ({used_percent:.1f}% used)")
            issues.append(f"Low disk space: {free_gb:.2f} GB free")
        elif free_gb < 5:
            click.echo(f"⚠️  Disk space: {free_gb:.2f} GB free ({used_percent:.1f}% used)")
            warnings.append(f"Low disk space: {free_gb:.2f} GB free")
        else:
            click.echo(f"✅ Disk space: {free_gb:.2f} GB free ({used_percent:.1f}% used)")
    except Exception:
        click.echo(f"⚠️  Disk space: Could not check")

    click.echo()
    click.echo("=" * 60)

    # Summary
    if not issues and not warnings:
        click.echo("Status: Healthy ✅")
        return 0
    elif issues:
        click.echo(f"Status: Unhealthy ({len(issues)} critical issues) ❌")
        for issue in issues:
            click.echo(f"  • {issue}")
        return 1
    else:
        click.echo(f"Status: Degraded ({len(warnings)} warnings) ⚠️")
        for warning in warnings:
            click.echo(f"  • {warning}")
        return 0


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()