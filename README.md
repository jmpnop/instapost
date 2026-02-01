# InstaPost - Instagram Automation

Automated Instagram posting via remote VM with cron-based scheduling.

## Architecture

```
Local (Mac/PC)                  Remote (AWS EC2)
┌─────────────────┐            ┌─────────────────────────────┐
│ instapost CLI   │◄── SSH ───►│ Cron Jobs                   │
│                 │            │ ├─ watcher (every 5 min)    │
│ Commands:       │            │ └─ scheduler (every 1 min)  │
│ - status        │            │                             │
│ - upload        │            │ S3 Bucket ◄─► /mnt/s3       │
│ - queue         │            │                             │
│ - logs          │            │ Angie ──► Cloudflare Tunnel │
│ - account       │            │ instapost.celestialtech.io  │
└─────────────────┘            └─────────────────────────────┘
```

## Features

- **Remote Operation**: CLI runs locally, all processing on VM
- **Cron Scheduling**: Reliable cron jobs with flock locking
- **Self-Hosted Images**: Angie + Cloudflare tunnel (no Dropbox)
- **S3 Storage**: Images stored in S3 Express bucket
- **AI Captions**: Optional caption generation via Claude CLI
- **Queue Management**: View, cancel, reschedule posts

## Quick Start

```bash
# Install
uv sync

# Setup (one-time)
cp .env.vm.example .env.vm
# Edit .env.vm with your API credentials
instapost init              # Upload credentials to VM
instapost deploy            # Deploy code

# Daily use
instapost upload photo.jpg  # Upload image
instapost status            # Check status
instapost queue             # View schedule
instapost logs -f           # Follow logs
```

## CLI Commands

### Status & Monitoring
| Command | Description |
|---------|-------------|
| `instapost status` | VM connection, cron jobs, queue stats |
| `instapost health` | Full health check |
| `instapost logs [-j watcher\|scheduler] [-f]` | View/follow logs |

### Queue Management
| Command | Description |
|---------|-------------|
| `instapost queue` | View scheduled posts |
| `instapost history` | View posted history |
| `instapost cancel <file>` | Cancel scheduled post |
| `instapost reschedule <file> <time>` | Change post time |
| `instapost rebalance [--apply]` | Fill schedule gaps |

### Images
| Command | Description |
|---------|-------------|
| `instapost images` | List pending images on VM |
| `instapost upload <path> [-c caption]` | Upload image to VM |

### Manual Execution
| Command | Description |
|---------|-------------|
| `instapost run watcher` | Run watcher manually |
| `instapost run scheduler` | Run scheduler manually |

### Instagram API
| Command | Description |
|---------|-------------|
| `instapost account` | Account info |
| `instapost media [-n N]` | Recent posts |
| `instapost token-info` | Token status |

### Deployment
| Command | Description |
|---------|-------------|
| `instapost init [file]` | Upload .env to VM |
| `instapost deploy` | Deploy code to VM |
| `instapost ssh` | Open SSH session |

## Configuration

### Local (.env)
```bash
VM_HOST=instapost-deploy
VM_INSTAPOST_DIR=/home/ironsirens/instapost
VM_IMAGES_DIR=/mnt/s3/images
VM_PROCESSED_DIR=/mnt/s3/processed
```

### Remote (.env.vm)
```bash
IMAGE_BASE_URL=https://instapost.celestialtech.io
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
FACEBOOK_ACCESS_TOKEN=...
INSTAGRAM_BUSINESS_ACCOUNT_ID=...
TIMEZONE=America/New_York
WEEKLY_SCHEDULE="0:07:00,2:11:00,4:17:00,5:09:00,6:18:00"
CAPTION_PROMPT="..."
```

## Cron Jobs

Installed via `crontab crontab.example` on the VM:

```cron
# Watcher: scan for new images every 5 minutes
*/5 * * * * flock -n /tmp/instapost-watcher.lock -c "..."

# Scheduler: post due images every minute
* * * * * flock -n /tmp/instapost-scheduler.lock -c "..."
```

- `flock -n` prevents overlapping runs
- Logs written to `~/instapost/logs/`
- Log rotation configured via `/etc/logrotate.d/instapost`

## How It Works

1. **Upload**: `instapost upload photo.jpg` copies image to `/mnt/s3/images/`
2. **Watcher**: Cron job scans for new images, validates, schedules to next slot
3. **Scheduler**: Cron job checks for due posts, posts via Instagram API
4. **Move**: After posting, image moved to `/mnt/s3/processed/{date}/`

## Captions

Three methods (in priority order):

1. **IPTC Metadata**: Caption stored in image metadata
2. **.txt File**: `photo.txt` alongside `photo.jpg`
3. **AI Generated**: Claude CLI generates caption (if installed)

## VM Setup

See [AWS EC2 Deployment](#aws-ec2-deployment) section for:
- EC2 instance setup
- S3 bucket mounting
- Angie web server
- Cloudflare tunnel
- Cron job installation

## Requirements

- Python 3.13+
- uv package manager
- SSH access to VM
- Facebook App with Instagram permissions

## License

MIT
