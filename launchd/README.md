# LaunchAgent Configuration for InstaPost Daemons

This directory contains macOS launchd configuration files (`.plist`) that ensure InstaPost daemons:
- **Start automatically** on login/boot
- **Never stop running** - automatically restart on crashes
- **Survive network errors** - resilient daemon architecture + OS-level supervision

## Quick Setup

```bash
# 1. Install the launchd agents
uv run instapost install-launchd

# 2. Start all daemons
uv run instapost start

# 3. Check status
uv run instapost status
```

## Manual Installation

If you prefer to install manually:

```bash
# Copy plist files to LaunchAgents directory
cp launchd/*.plist ~/Library/LaunchAgents/

# Load each service
launchctl load ~/Library/LaunchAgents/com.instapost.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.instapost.watcher.plist
launchctl load ~/Library/LaunchAgents/com.instapost.mover.plist

# Start services
launchctl start com.instapost.scheduler
launchctl start com.instapost.watcher
launchctl start com.instapost.mover
```

## What Each Service Does

### com.instapost.scheduler
- **Monitors**: `schedule.json` for posts that are due
- **Action**: Posts images to Instagram at scheduled times
- **Restart**: Auto-restarts on crash, with 10s throttle interval

### com.instapost.watcher
- **Monitors**: `images/` directory for new files
- **Action**: Schedules new images for posting
- **Restart**: Auto-restarts on crash, with 10s throttle interval

### com.instapost.mover
- **Monitors**: `processed.json` for completed posts
- **Action**: Moves posted images to `processed/` directory
- **Restart**: Auto-restarts on crash, with 10s throttle interval

## Configuration Details

Each plist file configures:
- **KeepAlive**: Ensures daemon restarts automatically
  - `SuccessfulExit: false` - Restart even on clean exit (unless explicitly stopped)
  - `Crashed: true` - Always restart on crashes
- **ThrottleInterval**: 10 seconds between restart attempts
- **ExitTimeOut**: 30 seconds for graceful shutdown
- **Logs**: Stdout/stderr captured in `logs/*.stdout.log` and `logs/*.stderr.log`

## Management Commands

```bash
# Check if services are loaded
launchctl list | grep instapost

# Check service status
launchctl print gui/$UID/com.instapost.scheduler

# View logs
tail -f logs/scheduler.stdout.log logs/scheduler.stderr.log

# Stop a service (temporarily)
launchctl stop com.instapost.scheduler

# Start a service
launchctl start com.instapost.scheduler

# Disable a service (won't start on boot)
launchctl unload ~/Library/LaunchAgents/com.instapost.scheduler.plist

# Re-enable a service
launchctl load ~/Library/LaunchAgents/com.instapost.scheduler.plist
```

## Uninstall

```bash
# Unload and remove all services
uv run instapost uninstall-launchd

# Or manually:
launchctl unload ~/Library/LaunchAgents/com.instapost.scheduler.plist
launchctl unload ~/Library/LaunchAgents/com.instapost.watcher.plist
launchctl unload ~/Library/LaunchAgents/com.instapost.mover.plist
rm ~/Library/LaunchAgents/com.instapost.*.plist
```

## Troubleshooting

### Service won't start
```bash
# Check logs for errors
tail -50 logs/scheduler.stderr.log

# Verify plist syntax
plutil -lint ~/Library/LaunchAgents/com.instapost.scheduler.plist

# Check permissions
ls -l ~/Library/LaunchAgents/com.instapost.*.plist
# Should be: -rw-r--r--  (644)
```

### Service keeps restarting
```bash
# Check recent logs
tail -100 logs/scheduler.stdout.log

# Check heartbeat (should update every ~60s)
cat .scheduler.heartbeat
date -r .scheduler.heartbeat

# If heartbeat is old, daemon is hung - kill and let launchd restart
pkill -9 -f instapost.daemons.scheduler
```

### Service not restarting after crash
```bash
# Check if loaded
launchctl list | grep instapost

# Reload the service
launchctl unload ~/Library/LaunchAgents/com.instapost.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.instapost.scheduler.plist
```

## Architecture Benefits

**Dual-Layer Resilience:**
1. **Application Layer** (ResilientDaemon class):
   - Catches all exceptions
   - Exponential backoff on errors
   - Never exits except on SIGTERM/SIGINT
   - Heartbeat monitoring

2. **OS Layer** (launchd):
   - Restarts process if it crashes completely
   - Starts on boot/login
   - Process monitoring
   - Resource limits

**Result**: Daemons will NEVER stop running, even after:
- Network failures
- API errors
- File system issues
- Out of memory crashes
- System reboots
- User login/logout

## Notes

- **Throttling**: launchd waits 10 seconds between restart attempts to prevent tight crash loops
- **Graceful Shutdown**: Daemons have 30 seconds to clean up before being force-killed
- **Environment**: `.env` variables are loaded by the Python process, not by launchd
- **Logs**: Both application logs (`logs/*.log`) and launchd logs (`logs/*.stdout.log`, `logs/*.stderr.log`) are kept
- **Heartbeat**: `.{daemon}.heartbeat` files updated every iteration to detect hung processes
