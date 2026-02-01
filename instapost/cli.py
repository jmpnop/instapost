"""Command-line interface for instapost - remote VM operations."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from instapost.version import __version__, __build__
from instapost import remote


@click.group()
@click.version_option(version=f"{__version__} (build {__build__})")
def cli():
    """InstaPost - Instagram automation via remote VM."""
    pass


# =============================================================================
# Status & Monitoring Commands
# =============================================================================

@cli.command()
def status():
    """Check status of remote VM and cron jobs."""
    click.echo("InstaPost Status")
    click.echo("=" * 50)
    click.echo()

    config = remote.get_vm_config()
    click.echo(f"VM Host: {config['host']}")
    click.echo()

    # Check SSH connectivity
    success, output = remote.ssh("echo 'connected'", timeout=5)
    if not success:
        click.echo("❌ Cannot connect to VM")
        click.echo(f"   {output}")
        sys.exit(1)
    click.echo("✅ VM: Connected")

    # Check cron jobs
    success, crontab = remote.check_cron()
    if success and 'instapost' in crontab:
        cron_count = crontab.count('instapost.cron')
        click.echo(f"✅ Cron: {cron_count} job(s) installed")
    else:
        click.echo("❌ Cron: No jobs installed")

    # Check schedule
    success, schedule_json = remote.read_json("schedule.json")
    if success:
        try:
            scheduled = json.loads(schedule_json)
            click.echo(f"📅 Scheduled: {len(scheduled)} post(s)")
        except json.JSONDecodeError:
            click.echo("⚠️  Schedule: Invalid JSON")

    # Check processed
    success, processed_json = remote.read_json("processed.json")
    if success:
        try:
            processed = json.loads(processed_json)
            click.echo(f"✅ Posted: {len(processed)} post(s)")
        except json.JSONDecodeError:
            pass

    # Check images directory
    success, images = remote.list_images()
    if success and images:
        count = len([f for f in images.split('\n') if f.strip()])
        click.echo(f"🖼️  Images: {count} file(s) pending")
    else:
        click.echo("🖼️  Images: 0 files pending")

    click.echo()
    click.echo(f"Version: v{__version__} (build {__build__})")


@cli.command()
def health():
    """Comprehensive health check of the remote system."""
    click.echo("InstaPost Health Check")
    click.echo("=" * 50)
    click.echo()

    issues = []
    warnings = []

    # SSH connectivity
    success, _ = remote.ssh("true", timeout=5)
    if success:
        click.echo("✅ SSH connectivity: OK")
    else:
        click.echo("❌ SSH connectivity: Failed")
        issues.append("Cannot connect to VM")
        click.echo()
        click.echo(f"Status: Unhealthy ({len(issues)} issues)")
        sys.exit(1)

    # Cron daemon
    success, output = remote.ssh("systemctl is-active crond")
    if success and 'active' in output:
        click.echo("✅ Cron daemon: Running")
    else:
        click.echo("❌ Cron daemon: Not running")
        issues.append("Cron daemon not running")

    # Cron jobs installed
    success, crontab = remote.check_cron()
    if success and 'instapost.cron.watcher_cron' in crontab:
        click.echo("✅ Watcher cron: Installed")
    else:
        click.echo("❌ Watcher cron: Not installed")
        issues.append("Watcher cron not installed")

    if success and 'instapost.cron.scheduler_cron' in crontab:
        click.echo("✅ Scheduler cron: Installed")
    else:
        click.echo("❌ Scheduler cron: Not installed")
        issues.append("Scheduler cron not installed")

    # Disk space
    success, df_output = remote.disk_usage()
    if success:
        lines = df_output.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 5:
                use_percent = parts[4].rstrip('%')
                try:
                    if int(use_percent) > 90:
                        click.echo(f"❌ Disk usage: {use_percent}%")
                        issues.append(f"Disk usage critical: {use_percent}%")
                    elif int(use_percent) > 80:
                        click.echo(f"⚠️  Disk usage: {use_percent}%")
                        warnings.append(f"Disk usage high: {use_percent}%")
                    else:
                        click.echo(f"✅ Disk usage: {use_percent}%")
                except ValueError:
                    pass

    # Web server (Angie)
    success, output = remote.ssh("systemctl is-active angie")
    if success and 'active' in output:
        click.echo("✅ Web server (Angie): Running")
    else:
        click.echo("❌ Web server (Angie): Not running")
        issues.append("Angie web server not running")

    # Cloudflare tunnel
    success, output = remote.ssh("systemctl is-active cloudflared")
    if success and 'active' in output:
        click.echo("✅ Cloudflare tunnel: Running")
    else:
        click.echo("⚠️  Cloudflare tunnel: Not running (may be managed differently)")
        warnings.append("Cloudflare tunnel status unknown")

    # S3 mount (check /mnt/s3 which is the actual mount point)
    success, output = remote.ssh("mountpoint -q /mnt/s3 && echo 'mounted' || (ls /mnt/s3 >/dev/null 2>&1 && echo 'accessible')")
    if success and ('mounted' in output or 'accessible' in output):
        click.echo("✅ S3 mount: OK")
    else:
        click.echo("❌ S3 mount: Not mounted")
        issues.append("S3 bucket not mounted")

    click.echo()
    click.echo("=" * 50)

    if issues:
        click.echo(f"Status: Unhealthy ({len(issues)} issues)")
        for issue in issues:
            click.echo(f"  ❌ {issue}")
        sys.exit(1)
    elif warnings:
        click.echo(f"Status: Degraded ({len(warnings)} warnings)")
        for warning in warnings:
            click.echo(f"  ⚠️  {warning}")
    else:
        click.echo("Status: Healthy ✅")


@cli.command()
@click.option('--job', '-j', type=click.Choice(['watcher', 'scheduler', 'all']), default='all',
              help='Which job logs to view')
@click.option('--lines', '-n', type=int, default=50, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(job, lines, follow):
    """View cron job logs from the remote VM."""
    log_files = {
        'watcher': 'watcher_cron.log',
        'scheduler': 'scheduler_cron.log',
    }

    jobs = list(log_files.keys()) if job == 'all' else [job]

    if follow:
        config = remote.get_vm_config()
        log_paths = ' '.join(f"{config['instapost_dir']}/logs/{log_files[j]}" for j in jobs)
        cmd = f"tail -f {log_paths}"
        try:
            import subprocess
            subprocess.run(['ssh', config['host'], cmd])
        except KeyboardInterrupt:
            click.echo("\nStopped following logs")
        return

    for j in jobs:
        if len(jobs) > 1:
            click.echo(f"{'=' * 50}")
            click.echo(f"{j.upper()} LOG")
            click.echo(f"{'=' * 50}")

        success, output = remote.tail_log(log_files[j], lines)
        if success:
            click.echo(output)
        else:
            click.echo(f"Error reading log: {output}")

        if len(jobs) > 1:
            click.echo()


# =============================================================================
# Queue Management Commands
# =============================================================================

@cli.command()
def queue():
    """View scheduled posts queue."""
    success, schedule_json = remote.read_json("schedule.json")
    if not success:
        click.echo("Error reading schedule")
        sys.exit(1)

    try:
        scheduled = json.loads(schedule_json)
    except json.JSONDecodeError:
        click.echo("Invalid schedule file")
        sys.exit(1)

    if not scheduled:
        click.echo("No posts scheduled")
        return

    click.echo("Scheduled Posts Queue")
    click.echo("=" * 60)
    click.echo()

    now = datetime.now()
    for i, entry in enumerate(scheduled, 1):
        filename = entry.get('filename', 'Unknown')
        scheduled_time = entry.get('time', 'Unknown')

        try:
            dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
            time_str = dt.strftime('%a %b %d, %Y at %H:%M')

            # Calculate countdown
            time_diff = dt.replace(tzinfo=None) - now
            if time_diff.total_seconds() > 0:
                days = time_diff.days
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if days > 0:
                    countdown = f"in {days}d {hours}h"
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
        click.echo(f"   {time_str}")
        click.echo()


@cli.command()
@click.option('--limit', '-n', type=int, default=10, help='Number of posts to show')
def history(limit):
    """View post history."""
    success, processed_json = remote.read_json("processed.json")
    if not success:
        click.echo("Error reading history")
        sys.exit(1)

    try:
        processed = json.loads(processed_json)
    except json.JSONDecodeError:
        click.echo("Invalid history file")
        sys.exit(1)

    if not processed:
        click.echo("No posts in history")
        return

    click.echo(f"Post History (last {min(limit, len(processed))})")
    click.echo("=" * 60)
    click.echo()

    for entry in list(reversed(processed))[:limit]:
        filename = entry.get('filename', 'Unknown')
        url = entry.get('url', 'No URL')
        timestamp = entry.get('timestamp', '')

        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%a %b %d, %Y at %H:%M')
        except Exception:
            time_str = timestamp

        click.echo(f"📷 {filename}")
        click.echo(f"   Posted: {time_str}")
        click.echo(f"   URL: {url}")
        click.echo()


@cli.command()
@click.argument('filename')
def cancel(filename):
    """Cancel a scheduled post."""
    success, schedule_json = remote.read_json("schedule.json")
    if not success:
        click.echo("Error reading schedule")
        sys.exit(1)

    try:
        scheduled = json.loads(schedule_json)
    except json.JSONDecodeError:
        click.echo("Invalid schedule file")
        sys.exit(1)

    original_count = len(scheduled)
    scheduled = [e for e in scheduled if e.get('filename') != filename]

    if len(scheduled) == original_count:
        click.echo(f"Not found: {filename}")
        sys.exit(1)

    success, _ = remote.write_json("schedule.json", json.dumps(scheduled, indent=2))
    if success:
        click.echo(f"✅ Cancelled: {filename}")
        click.echo(f"   Remaining: {len(scheduled)} post(s)")
    else:
        click.echo("Error updating schedule")
        sys.exit(1)


@cli.command()
@click.argument('filename')
@click.argument('new_time')
def reschedule(filename, new_time):
    """Reschedule a post to a different time.

    NEW_TIME format: YYYY-MM-DDTHH:MM:SS
    """
    # Validate time format
    try:
        datetime.fromisoformat(new_time)
    except ValueError:
        click.echo("Invalid time format. Use: YYYY-MM-DDTHH:MM:SS")
        sys.exit(1)

    success, schedule_json = remote.read_json("schedule.json")
    if not success:
        click.echo("Error reading schedule")
        sys.exit(1)

    try:
        scheduled = json.loads(schedule_json)
    except json.JSONDecodeError:
        click.echo("Invalid schedule file")
        sys.exit(1)

    found = False
    old_time = None
    for entry in scheduled:
        if entry.get('filename') == filename:
            old_time = entry.get('time')
            entry['time'] = new_time
            found = True
            break

    if not found:
        click.echo(f"Not found: {filename}")
        sys.exit(1)

    success, _ = remote.write_json("schedule.json", json.dumps(scheduled, indent=2))
    if success:
        click.echo(f"✅ Rescheduled: {filename}")
        if old_time:
            click.echo(f"   Old: {old_time}")
        click.echo(f"   New: {new_time}")
    else:
        click.echo("Error updating schedule")
        sys.exit(1)


# =============================================================================
# Image Commands
# =============================================================================

@cli.command()
def images():
    """List pending images on the remote VM."""
    success, output = remote.list_images()
    if not success:
        click.echo("Error listing images")
        sys.exit(1)

    files = [f for f in output.split('\n') if f.strip()]

    if not files:
        click.echo("No pending images")
        return

    click.echo(f"Pending Images ({len(files)})")
    click.echo("=" * 40)
    for f in files:
        click.echo(f"  {f}")


@cli.command()
@click.argument('image_path', type=click.Path(exists=True))
@click.option('--caption', '-c', help='Caption text or path to .txt file')
def upload(image_path, caption):
    """Upload an image to the remote VM for scheduling."""
    click.echo(f"Uploading {image_path}...")

    success, remote_path = remote.upload_image(image_path)
    if not success:
        click.echo(f"Error uploading: {remote_path}")
        sys.exit(1)

    click.echo(f"✅ Uploaded to: {remote_path}")

    # Upload caption if provided
    if caption:
        if os.path.isfile(caption):
            with open(caption) as f:
                caption_text = f.read()
        else:
            caption_text = caption

        # Upload caption as .txt file alongside image
        config = remote.get_vm_config()
        base = os.path.splitext(os.path.basename(image_path))[0]
        caption_path = f"{config['images_dir']}/{base}.txt"

        escaped = caption_text.replace("'", "'\"'\"'")
        success, _ = remote.ssh(f"echo '{escaped}' > {caption_path}")
        if success:
            click.echo(f"✅ Caption uploaded")
        else:
            click.echo("⚠️  Failed to upload caption")

    click.echo()
    click.echo("Run watcher to schedule: instapost run watcher")


# =============================================================================
# Manual Run Commands
# =============================================================================

@cli.command()
@click.argument('job', type=click.Choice(['watcher', 'scheduler']))
def run(job):
    """Manually run a cron job on the remote VM."""
    click.echo(f"Running {job}...")

    module = f"{job}_cron"
    success, output = remote.run_cron_module(module)

    if output:
        click.echo(output)

    if success:
        click.echo(f"✅ {job.capitalize()} completed")
    else:
        click.echo(f"❌ {job.capitalize()} failed")
        sys.exit(1)


@cli.command()
@click.option('--apply', is_flag=True, help='Apply changes (default is dry-run)')
def rebalance(apply):
    """Rebalance schedule to fill gaps."""
    config = remote.get_vm_config()
    cmd = f"cd {config['instapost_dir']} && ~/.local/bin/uv run python -m instapost.rebalance"
    if apply:
        cmd += " --apply"

    success, output = remote.ssh(cmd, timeout=60)

    if output:
        click.echo(output)

    if not success:
        click.echo("Rebalance failed")
        sys.exit(1)


# =============================================================================
# Instagram API Commands (run on remote VM)
# =============================================================================

@cli.command()
def token_info():
    """Check Facebook token validity and expiration."""
    config = remote.get_vm_config()
    cmd = f"cd {config['instapost_dir']} && ~/.local/bin/uv run python -m instapost.api_commands token-info"
    success, output = remote.ssh(cmd, timeout=30)
    if output:
        click.echo(output)
    if not success:
        sys.exit(1)


@cli.command()
def account():
    """Get Instagram account information."""
    config = remote.get_vm_config()
    cmd = f"cd {config['instapost_dir']} && ~/.local/bin/uv run python -m instapost.api_commands account"
    success, output = remote.ssh(cmd, timeout=30)
    if output:
        click.echo(output)
    if not success:
        sys.exit(1)


@cli.command()
@click.option('--limit', '-n', type=int, default=5, help='Number of posts to show')
def media(limit):
    """Get recent Instagram posts."""
    config = remote.get_vm_config()
    cmd = f"cd {config['instapost_dir']} && ~/.local/bin/uv run python -m instapost.api_commands media {limit}"
    success, output = remote.ssh(cmd, timeout=30)
    if output:
        click.echo(output)
    if not success:
        sys.exit(1)


# =============================================================================
# Deployment Commands
# =============================================================================

@cli.command()
@click.argument('env_file', type=click.Path(exists=True), required=False)
def init(env_file):
    """Initialize remote VM with .env file.

    ENV_FILE is the path to the .env file to upload (default: .env.vm)
    """
    import subprocess

    config = remote.get_vm_config()

    # Find env file to upload
    if not env_file:
        for candidate in ['.env.vm', '.env.vm.example']:
            path = Path(__file__).parent.parent / candidate
            if path.exists():
                env_file = str(path)
                break

    if not env_file:
        click.echo("No .env file found. Create .env.vm with your credentials.")
        click.echo("See .env.vm.example for template.")
        sys.exit(1)

    click.echo(f"Uploading {env_file} to VM...")

    remote_path = f"{config['instapost_dir']}/.env"
    result = subprocess.run(
        ['scp', env_file, f"{config['host']}:{remote_path}"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        click.echo(f"✅ Uploaded to {remote_path}")
    else:
        click.echo(f"❌ Failed: {result.stderr}")
        sys.exit(1)


@cli.command()
def deploy():
    """Deploy code to the remote VM."""
    import subprocess

    deploy_script = Path(__file__).parent.parent / "deploy.sh"
    if not deploy_script.exists():
        click.echo("deploy.sh not found")
        sys.exit(1)

    click.echo("Deploying to VM...")
    result = subprocess.run([str(deploy_script)], cwd=deploy_script.parent)
    sys.exit(result.returncode)


@cli.command()
def ssh():
    """Open SSH session to the remote VM."""
    import subprocess

    config = remote.get_vm_config()
    subprocess.run(['ssh', config['host']])


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
