# InstaPost - Instagram Posting Automation

<img width="2912" height="1632" alt="InstaPost Screenshot" src="instapost.png" />

A command-line tool for automating the scheduling and posting of images to Instagram using Facebook Graph API and Dropbox.

## Features

### Core Automation
- **Automated Scheduling**: Drop images, auto-scheduled to next available slot
- **Directory Monitoring**: Watches for new images in real-time
- **Smart Posting**: Posts at scheduled times via Facebook Graph API
- **Caption Support**: Add captions via simple `.txt` files
- **Automatic Organization**: Processed files moved to dated folders

### Queue & Schedule Management
- **Queue Viewing**: See all scheduled posts with countdown timers
- **Flexible Rescheduling**: Change post times on the fly
- **Cancellation**: Remove posts from queue anytime
- **Schedule Rebalancing**: Automatically fills gaps by moving future posts earlier
- **Schedule Validation**: Prevents past times and conflicts
- **Weekly Schedule**: Configure custom posting times per day

### Reliability & Error Handling
- **Retry Logic**: Auto-retry API failures with exponential backoff (5 attempts)
- **Smart Image Validation**: Enforces Instagram requirements (dimensions, aspect ratio), auto-resizes oversized images
- **Process Safety**: Single-instance protection prevents conflicts
- **Health Monitoring**: System health checks (daemons, disk, schedule)

### Monitoring & Debugging
- **Real-time Logs**: View daemon logs with filtering and follow mode
- **Post History**: View past posts with URLs and timestamps
- **Status Dashboard**: Check daemon status, runtime, and mode
- **Clean Logs**: Idle animation only in terminal (not log files)

### Modes & Testing
- **Production Mode**: Follows weekly schedule (default)
- **Test Mode**: Process immediately for testing
- **Cloud Integration**: Dropbox for image hosting

## Core Components

### 1. Watcher (`instapost/daemons/watcher.py`)
- Monitors specified directories for new images
- Validates image files (JPG, PNG only)
- Maintains schedule in `schedule.json`
- Implements process safety to prevent multiple instances
- Shows idle animation when waiting for changes

### 2. Scheduler (`instapost/daemons/scheduler.py`)
- Processes scheduled posts according to `WEEKLY_SCHEDULE`
- **Production Mode** (default): Follows the weekly schedule
- **Test Mode**: When `TEST_MODE=true` environment variable is set, processes all posts immediately
- Handles complete posting workflow:
  1. Validates scheduled times
  2. Processes images through Dropbox upload (via `clients/dropbox.py`)
  3. Posts to Instagram via Facebook Graph API (via `clients/instagram.py`)
  4. Updates `processed.json`

### 3. Mover (`instapost/daemons/mover.py`)
- Monitors `processed.json` for completed posts
- Organizes processed files into dated directories
- Keeps working directory clean

## 📁 Project Structure

```
instapost/
├── instapost/                      # Main Python package
│   ├── cli.py                      # CLI interface (Click framework)
│   ├── config.py                   # Pydantic configuration models
│   ├── settings.py                 # Timezone & weekly schedule parsing
│   ├── utils.py                    # JSON I/O, logging, process safety
│   ├── validation.py               # Image validation (Instagram requirements)
│   ├── retry.py                    # Exponential backoff retry decorator
│   ├── schedule_utils.py           # Schedule validation & management
│   ├── generate_captions.py        # AI-powered caption generation
│   │
│   ├── daemons/                    # Long-running processes
│   │   ├── watcher.py              # File system monitoring daemon
│   │   ├── scheduler.py            # Post processing daemon
│   │   └── mover.py                # File organization daemon
│   │
│   ├── clients/                    # API clients
│   │   ├── dropbox.py              # Dropbox upload & link generation
│   │   ├── instagram.py            # Instagram posting via Graph API
│   │   └── facebook.py             # Facebook token validation
│   │
│   └── tools/                      # CLI utilities
│       ├── db_token.py             # Dropbox OAuth2 authentication
│       ├── fb_token.py             # Facebook token inspection
│       └── image_gen.py            # Test image generator
│
├── test/                           # Test scripts
│   ├── dropbox_api.py              # Dropbox API integration test
│   ├── facebook_api.py             # Facebook token validation test
│   ├── instagram_api.py            # Instagram posting test
│   └── scheduler.py                # Scheduler workflow test
│
├── images/                         # Input: images to post
├── processed/                      # Output: organized by date (YYYY-MM-DD)
├── logs/                           # Application logs (daily rotation)
├── schedule.json                   # Current posting schedule
├── processed.json                  # Log of processed posts
├── db_token.json                   # Dropbox OAuth token storage
├── .env                            # Credentials (never commit!)
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── pyproject.toml                  # Python project configuration
├── README.md                       # This file
└── README.ru.md                    # Russian documentation
```

## Installation

### Prerequisites
- Python 3.13+
- Required packages: `psutil`, `Pillow`, `watchdog`, `python-dotenv`, `requests`, `pydantic`, `click`, `python-dateutil`
- Dropbox API credentials
- Facebook Developer account with Instagram Graph API access

1. **Install Homebrew**:
   ```bash
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. **Install Python and UV**:
   ```bash
   brew install uv
   uv python install 3.13.2
   ```
3. **Install Git**:
   ```bash
   brew install git
   ```

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jmpnop/instapost.git
   cd instapost
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Create required directories**:
   ```bash
   mkdir -p images processed logs
   ```

## Configuration

### Setting up Dropbox API

1. Go to the [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2. Create a new app with the following settings:
   - API: Dropbox API
   - Access type: Full Dropbox
   - Permissions: files.content.write, files.content.read, sharing.write
3. Note your DROPBOX_APP_KEY and App DROPBOX_APP_SECRET
4. Run the setup command to get your DROPBOX_REFRESH_TOKEN:

```bash
python -m instapost.cli dropbox
```

5. Follow the instructions to authorize the app and get your refresh token
6. Add the refresh token to your `.env` file
7. Navigate to the folder in Dropbox that will store your images. Copy its full path exactly as shown in Dropbox (e.g. /InstagramPosts or /Apps/InstaPost/images).
8. Add the DROPBOX_FOLDER_PATH  to your `.env` file

### Setting up Facebook Graph API

This guide shows you how to get a **Page Access Token** that **never expires** - the best option for automated Instagram posting.

**Benefits:**
- ✅ **Never expires** (no maintenance needed)
- ✅ **No refresh scripts required**
- ✅ **Set it once, forget it forever**

#### Prerequisites

Before starting, ensure you have:
- ✅ Facebook Developer account → https://developers.facebook.com/
- ✅ Facebook Page (must be admin/owner)
- ✅ Instagram Business Account linked to your Facebook Page
- ✅ Facebook App created with Instagram permissions

#### Step 1: Get Short-Lived User Access Token

**URL:** https://developers.facebook.com/tools/explorer/

1. Select your **App** from the "Meta App" dropdown on the right panel
2. Under "User or Page" dropdown, select **"User Token"**
3. In the **Permissions** section on the right, check these permissions:
   - ✅ `instagram_basic`
   - ✅ `instagram_content_publish`
   - ✅ `pages_read_engagement`
   - ✅ `pages_manage_metadata` (or `pages_show_list`)
4. Click the blue **"Generate Access Token"** button
5. Follow the prompts to authorize your app (Facebook will ask to connect your Page)
6. **Copy the token** from the "Access Token" field - it will look like: `EAFWhIOznvsEBO...`

**Note:** This token expires in 1 hour, but we'll exchange it immediately in Step 2.

#### Step 2: Exchange for Long-Lived User Token

**Open Terminal and run:**

```bash
curl -X POST "https://graph.facebook.com/v18.0/oauth/access_token" \
  -d "grant_type=fb_exchange_token" \
  -d "client_id=YOUR_APP_ID" \
  -d "client_secret=YOUR_APP_SECRET" \
  -d "fb_exchange_token=PASTE_TOKEN_FROM_STEP_1"
```

**Replace:**
- `YOUR_APP_ID` - Your Facebook App ID
- `YOUR_APP_SECRET` - Your Facebook App Secret
- `PASTE_TOKEN_FROM_STEP_1` - The token from Step 1

**Response:**
```json
{
  "access_token": "EAABsbCS1iHgBO...",
  "token_type": "bearer",
  "expires_in": 5183944
}
```

**Copy the `access_token`** - you'll use it in Step 3.

#### Step 3: Get Page Access Token (Never Expires!)

**Run this command:**

```bash
curl "https://graph.facebook.com/v18.0/me/accounts?access_token=PASTE_LONG_LIVED_TOKEN_FROM_STEP_2"
```

**Replace:**
- `PASTE_LONG_LIVED_TOKEN_FROM_STEP_2` - The token from Step 2

**Response:**
```json
{
  "data": [
    {
      "access_token": "EAABsbCS1iHgBO...NEVER_EXPIRES",
      "category": "Brand",
      "name": "Your Page Name",
      "id": "123456789"
    }
  ]
}
```

**🎉 The `access_token` in this response is your Page Access Token - it NEVER EXPIRES!**

#### Step 4: Get Instagram Business Account ID

**Run this command:**

```bash
curl "https://graph.facebook.com/v18.0/me?fields=instagram_business_account&access_token=YOUR_PAGE_TOKEN"
```

**Replace:**
- `YOUR_PAGE_TOKEN` - The Page Access Token from Step 3

**Response:**
```json
{
  "instagram_business_account": {
    "id": "1234567890123456"
  }
}
```

Use the `instagram_business_account.id` as your `INSTAGRAM_BUSINESS_ACCOUNT_ID`.

#### Step 5: Update Your .env File

Add these credentials to your `.env` file:

```bash
# Facebook/Instagram Configuration
FACEBOOK_APP_ID=your_app_id_here
FACEBOOK_APP_SECRET=your_app_secret_here
FACEBOOK_ACCESS_TOKEN=your_page_access_token_from_step_3
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_account_id_from_step_4
```

**✅ Done! This token will work forever (as long as your app and page remain active).**

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Dropbox Configuration
# 1. Get these from your Dropbox App at https://www.dropbox.com/developers/apps
DROPBOX_APP_KEY=your_dropbox_app_key         # From Dropbox App Console -> App Key
DROPBOX_APP_SECRET=your_dropbox_app_secret   # From Dropbox App Console -> App Secret
# 2. Get this by running: python -m instapost.cli dropbox
DROPBOX_REFRESH_TOKEN=your_dropbox_refresh_token
DROPBOX_FOLDER_PATH=your_dropbox_folder_path

# Facebook/Instagram Configuration
# 1. Get these from Facebook Developer Portal: https://developers.facebook.com/
FACEBOOK_APP_ID=your_facebook_app_id           # From Facebook App Dashboard
FACEBOOK_APP_SECRET=your_facebook_app_secret   # From Facebook App Dashboard
FACEBOOK_ACCESS_TOKEN=your_facebook_access_token  # Long-lived access token with required permissions
# 2. Find your Instagram Business Account ID using:
#    - Go to https://developers.facebook.com/tools/explorer/
#    - Select your app and get user accounts with: /me/accounts
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_account_id

# Scheduling
TIMEZONE=America/New_York
WEEKLY_SCHEDULE="0:07:00,2:11:00,4:17:00,5:09:00,6:18:00"
```

## 📅 Weekly Schedule Format

Format: `WEEKLY_SCHEDULE="0:07:00,2:11:00,4:17:00,5:09:00,6:18:00"`

- Days: 0=Monday, 1=Tuesday, ..., 6=Sunday
- Times in 24-hour format (HH:MM:SS)
- Example schedule:
  - Monday (0): 07:00
  - Wednesday (2): 11:00
  - Friday (4): 17:00
  - Saturday (5): 09:00
  - Sunday (6): 18:00

## 🛠️ Usage

**The `instapost` CLI is the universal command center for all operations.**

**All commands use `uv run` to execute in the virtual environment:**

### Quick Start
```bash
# Start all daemons (watcher, scheduler, mover)
uv run instapost start

# Check status
uv run instapost status

# Stop all daemons
uv run instapost stop
```

### Daemon Management
```bash
uv run instapost start          # Start all daemons
uv run instapost stop           # Stop all daemons
uv run instapost status         # Check daemon status
uv run instapost restart        # Restart all daemons
uv run instapost health         # System health check
```

### Queue Management
```bash
uv run instapost queue                              # View scheduled posts
uv run instapost cancel <filename>                  # Remove from schedule
uv run instapost reschedule <filename> <new-time>   # Change post time
uv run instapost rebalance                          # Preview schedule optimization
uv run instapost rebalance --apply                  # Optimize schedule (fill gaps)
```

### Schedule Rebalancing

**Automatically optimize your posting schedule by filling gaps:**

The rebalance command identifies empty time slots in your weekly schedule and fills them by moving posts from further in the future to earlier available slots.

**When to use:**
- After canceling or removing posts (creates gaps in schedule)
- When system was down and missed posting times
- To compact the schedule and post images sooner

**How it works:**
```bash
# Preview what would change (dry-run)
uv run instapost rebalance

# Output:
# Gaps found: 260
# Posts to move: 76
# Would move 76 posts to fill 260 gaps
#
# Changes (first 10):
# 0d6242d9-59e9-48d3-aa88-9dfe003415c3.jpg
#   2026-01-28 11:00 → 2026-01-23 17:00

# Apply the rebalancing
uv run instapost rebalance --apply
```

**Safety features:**
- Always runs in dry-run mode by default (preview changes first)
- Only moves unprocessed posts (already posted images stay in history)
- Preserves chronological order (posts maintain relative ordering)
- Fills earliest gaps first (moves posts to soonest available slots)

### Monitoring
```bash
uv run instapost logs                   # View all daemon logs
uv run instapost logs -d scheduler      # View specific daemon
uv run instapost logs -f                # Follow logs in real-time
```

**Log Format:**
All log entries include PID and build number for debugging:
```
2026-01-12 16:26:04 [PID:18308] [Build:1768252962] - scheduler - INFO - Processing...
```
This helps identify:
- Which process generated the log
- Which code version is running
- Duplicate processes (different PIDs for same daemon)

### Account & Posts
```bash
uv run instapost info            # Get Instagram account info
uv run instapost media           # View recent posts
uv run instapost token-info     # Check token validity
uv run instapost history        # View posting history with URLs
uv run instapost history -n 25  # Last 25 posts
```

### Manual Posting
```bash
uv run instapost post path/to/image.jpg --caption "Your caption here"
```

### Advanced: Individual Daemon Control
> Only needed for debugging or custom setups. Use `instapost start` for normal operation.

```bash
# Start daemons individually
python -m instapost.daemons.watcher ./images
python -m instapost.daemons.scheduler
python -m instapost.daemons.mover ./images ./processed
```

### Test Mode
Set `TEST_MODE=true` in `.env` to process posts immediately (bypasses schedule):
```bash
# Edit .env
TEST_MODE=true

# Restart daemons to apply
uv run instapost restart
```

### Adding Captions to Posts

**InstaPost supports automatic caption detection via `.txt` files:**

```bash
# 1. Create a caption file with the same name as your image
echo "Beautiful sunset 🌅 #Photography #Nature" > images/sunset.txt

# 2. Add your image (watcher will detect both files)
cp ~/photos/sunset.jpg images/

# The post will be automatically scheduled with the caption
```

**Caption Format:**
- Plain text files (`.txt` extension)
- Must match image filename: `image.jpg` → `image.txt`
- Single-line or multi-line supported
- Supports emojis and hashtags
- **Optional** - if no `.txt` file, posts without caption

**Example with multi-line caption:**
```bash
cat > images/vacation.txt << 'EOF'
Amazing vacation in Hawaii! 🏝️

#Travel #Hawaii #Paradise #Vacation
#BeachLife #Summer2025
EOF

cp vacation.jpg images/
# Will be scheduled with the full multi-line caption
```

**How it works:**
1. Watcher detects both `image.jpg` and `image.txt`
2. Caption is read from `.txt` file
3. Caption stored in `schedule.json`
4. Scheduler passes caption to Instagram when posting

### AI Caption Generation

**Generate captions automatically using AI CLI:**

```bash
# Generate captions for all images in a directory
python -m instapost.generate_captions /path/to/images

# Example: generate captions for images in the watched directory
python -m instapost.generate_captions ./images
```

**How it works:**
- Scans directory for images (jpg, jpeg, png, gif, webp)
- Skips images that already have a `.txt` caption file
- Uses AI to analyze each image and generate a niche-appropriate caption
- Saves caption to `image.txt` alongside each `image.jpg`

**Example output:**
```
Found 5 image(s) in ./images
Skipping photo1.jpg - caption already exists
Processing photo2.jpg...
  Created photo2.txt
Processing photo3.jpg...
  Created photo3.txt
```

### Image Validation

**Images are automatically validated and processed against Instagram requirements:**

- **Dimensions**: 320px - 1440px (width and height)
- **File Size**: Maximum 8MB - **oversized images are automatically resized**
- **Aspect Ratio**: 0.8 to 1.91 (4:5 portrait to 1.91:1 landscape)
- **Format**: JPEG or PNG only

**Automatic Image Resizing:**
Images larger than 8MB are automatically resized before scheduling:
```
Image size (13.3MB) exceeds 8MB limit. Resizing...
Resizing from 5120x3413 to 3763x2508
Image resized to 1.9MB
```

**Invalid images are rejected with detailed error messages:**
```
Image validation failed: Aspect ratio too portrait: 0.5 (min 0.8)
Image validation failed: Image too small: 200x200 (min 320x320)
```

### Post History

**View your posting history:**
```bash
uv run instapost history          # Last 10 posts (default)
uv run instapost history -n 25    # Last 25 posts

# Output shows:
# 1. filename.jpg
#    Posted: Mon Dec 30, 2025 at 14:30:00
#    URL: https://www.instagram.com/p/ABC123/
```

### Reliability & Error Handling

**Automatic Retry Logic:**
- Instagram API calls automatically retry on failures
- **5 retry attempts** with exponential backoff (2s → 3s → 4.5s → 6.75s → 10s)
- Handles transient errors:
  - Media Not Found (Instagram processing delay)
  - Media Not Ready (container creation lag)
  - Network errors and timeouts
  - Rate limiting (HTTP 429)
  - Server errors (HTTP 500-504)

**Common scenarios handled:**
```
Attempt 1/5 failed: Media Not Found
Retrying in 2.0s...
Attempt 2/5 failed: Media Not Found
Retrying in 3.0s...
✅ Successfully posted to Instagram
```

**Schedule Validation:**
- Prevents scheduling posts in the past
- Detects time conflicts (multiple posts within 1 minute)
- Validates time format before saving

**Health Monitoring:**
```bash
uv run instapost health  # Check system health

# Reports on:
# - Daemon status (running/stopped)
# - Schedule file integrity
# - Directory existence
# - Disk space (warns if <5GB free)
```

## 📂 File Structure

### Core Directories
- `images/`: Directory for images to be posted
  - Files are processed in alphabetical order
  - Only JPG/PNG files are processed
  - Recommended max size: 8MB per file

- `processed/`: Successfully posted images are moved here
  - Organized by date (YYYY-MM-DD)
  - Original filenames are preserved
  - Contains metadata JSON for each image

- `logs/`: Log files
  - `instapost.log`: Main application log
  - `instapost.error.log`: Error-only log
  - Rotates daily, keeps logs for 7 days
  - Max size: 10MB per log file

### Configuration Files
- `.env`: Environment variables (never commit this!)
  - Contains sensitive credentials
  - Required for application startup
  - Use `chmod 600 .env` to secure it

### Data Files (automatically managed)
- `schedule.json`: Current posting schedule
  - Format: `{"next_post_time": "2023-01-01T12:00:00", "schedule": ["0:07:00", ...]}`
  - Automatically updated by the scheduler
  - Can be manually edited when services are stopped

- `processed.json`: Log of processed posts
  - Tracks which posts have been processed
  - Prevents duplicate posting
  - Format: `{"filename": {"posted_at": "timestamp", "status": "success|failed"}}`

- `db_token.json`: API tokens (automatically managed)
  - Stores OAuth tokens
  - Automatically refreshed as needed
  - Should be included in `.gitignore`

## 🔍 Troubleshooting

### Common Issues

1. **Duplicate Posts / Multiple Processes Running**
   - **Symptom**: Same image posted multiple times to Instagram
   - **Cause**: Multiple daemon processes running concurrently
   - **Check for duplicate processes:**
     ```bash
     # Check how many of each daemon are running
     ps -ef | grep "instapost.daemons" | grep -v grep

     # Should show EXACTLY 3 processes:
     # - 1 watcher
     # - 1 scheduler
     # - 1 mover
     ```
   - **Fix:**
     ```bash
     # Kill all instapost processes
     pkill -9 -f "instapost.daemons"

     # Wait a moment
     sleep 3

     # Start clean
     uv run instapost start

     # Verify only 3 processes
     ps -ef | grep "instapost.daemons" | grep -v grep | wc -l
     # Should output: 3
     ```
   - **Check logs for multiple PIDs:**
     ```bash
     # Logs now show [PID:12345] [Build:1768252962]
     # All entries for same daemon should have same PID
     grep "Processing scheduled post" logs/scheduler.log | tail -5

     # If you see different PIDs, you have duplicate processes
     ```

2. **Token Issues**
   - Verify token permissions:
     ```bash
     # Check token permissions in Facebook Developer Portal
     open https://developers.facebook.com/apps/
     ```
   - Check token expiration and permissions:
     ```bash
     # Check token status (replace with your token)
     curl -X GET "https://graph.facebook.com/v12.0/me?access_token=YOUR_ACCESS_TOKEN"
     ```
   - Regenerate tokens if needed:
     ```bash
     # Remove existing token file to trigger re-authentication
     rm db_token.json
     ```
   - Verify app permissions in Dropbox and Facebook Developer portals
   - Ensure your system clock is synchronized:
     ```bash
     # Check system time and timezone
     date
     timedatectl status  # Linux
     systemsetup -gettimezone  # macOS
     ```

2. **Posting Failures**
   - Check image format (only JPG/PNG supported):
     ```bash
     # Check file type and extension
     file your_image.jpg
     
     # List all non-JPG/PNG files in the directory
     find /path/to/images -type f ! \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \)
     ```
   - Verify image size (Instagram has size limits):
     ```bash
     # Install ImageMagick if needed: brew install imagemagick (macOS) or sudo apt-get install imagemagick (Linux)
     identify -format "%f: %wx%h %[size]\n" /path/to/your/image.jpg
     
     # Find images larger than 8MB (Instagram's limit is 8MB)
     find /path/to/images -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) -size +8M -exec ls -lh {} \;
     ```
   - Check network connectivity to required services:
     ```bash
     # Check connectivity to Facebook's API
     ping -c 4 graph.facebook.com
     
     # Check connectivity to Dropbox
     ping -c 4 api.dropboxapi.com
     
     # Check if HTTPS ports are open
     nc -zv graph.facebook.com 443
     nc -zv api.dropboxapi.com 443
     
     # Check DNS resolution
     nslookup graph.facebook.com
     nslookup api.dropboxapi.com
     ```
   - Ensure the image doesn't contain any restricted content:
     ```bash
     # Check image properties (install exiftool if needed)
     exiftool -g1 -a -s your_image.jpg
     
     # Check for common issues like incorrect color profiles
     identify -verbose your_image.jpg | grep -i profile
     
     # Check image dimensions (Instagram prefers between 320x320 and 1080x1350 pixels)
     identify -format "%f: %wx%h\n" your_image.jpg
     ```

3. **File Permissions**
   - Ensure the application has write access to all directories:
     ```bash
     # Check directory permissions
     ls -la
     
     # Set correct permissions (run from project root)
     chmod -R u+w .
     ```
   - Check disk space:
     ```bash
     # Check available disk space
     df -h .
     
     # Check large files (top 10)
     du -hs * | sort -rh | head -n 10
     ```

4. **Service Status**
   - Check if all services are running:
     ```bash
     ps aux | grep "instapost.daemons"
     ```
   - Verify network connectivity to required services
   - Check for any rate limiting from APIs

## 📋 Version Information

### Supported Versions
- **Python**: 3.13+ (recommended: 3.13.0 or later)
- **Facebook Graph API**: v18.0 (latest stable)
- **Dropbox API**: v2

### Compatibility
- Tested on macOS and Linux
- Requires x86_64 or ARM64 architecture

## Dependencies

### Python Version
- Python 3.13+ (recommended: 3.13.0 or later)

### Python Packages
Install all required packages with:
```bash
pip install -e .
```

Or manually install the dependencies:
```bash
pip install \
    dropbox \
    python-dotenv \
    requests \
    pydantic \
    click \
    python-dateutil \
    Pillow \
    watchdog \
    psutil
```

### System Dependencies
- A running system with a stable internet connection
- Sufficient disk space for your images and logs
- Proper file system permissions for the application to read/write files

## 🚀 Complete Workflow Example

1. **Set up your environment**:
   ```bash
   # Copy and edit .env file
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Start the system**:
   ```bash
   # Start all daemons in background
   uv run instapost start

   # Verify everything is running
   uv run instapost health
   ```

3. **Add images with captions** (optional):
   ```bash
   # Create caption files (optional)
   echo "My first automated post! 🚀 #InstaPost" > images/photo1.txt
   echo "Another great shot 📸 #Photography" > images/photo2.txt

   # Copy images to the watched directory
   cp ~/photos/photo1.jpg ./images/
   cp ~/photos/photo2.jpg ./images/

   # Watcher will detect both images and their captions
   # They'll be auto-scheduled to next available slots
   ```

4. **Monitor the queue**:
   ```bash
   # View scheduled posts
   uv run instapost queue

   # View post history
   uv run instapost history

   # Follow logs in real-time
   uv run instapost logs -f
   ```

5. **Manage the schedule**:
   ```bash
   # Reschedule a post
   uv run instapost reschedule photo1.jpg 2025-12-31T12:00:00

   # Cancel a post
   uv run instapost cancel photo2.jpg
   ```

## 🔒 Security Notes

1. **Secure your `.env` file**:
   - Never commit it to version control (it's in .gitignore by default)
   - Set restrictive permissions: `chmod 600 .env`

2. **API Rate Limits**:
   - Instagram Graph API has rate limits
   - The app includes basic rate limiting, but monitor your usage

3. **Token Security**:
   - Keep your access tokens secure
   - Rotate tokens periodically
   - Revoke unused tokens from your Dropbox and Facebook app dashboards

## 🛠 Maintenance

### Logs
- Logs are stored in the `logs/` directory
- Rotate logs regularly to prevent disk space issues
- Check logs for errors: `tail -f logs/instapost.log`

### Cleanup
```bash
# Remove old processed files (older than 30 days)
find processed/ -type f -mtime +30 -delete

# Clean up log files
find logs/ -type f -name "*.log" -mtime +7 -delete
```

### Backup
Regularly backup these important files:
- `.env` - Contains your API credentials
- `schedule.json` - Your posting schedule
- `processed.json` - Record of processed posts

## 📊 Monitoring

1. **Check service status**:
   ```bash
   # Check if processes are running
   ps aux | grep "instapost.daemons"
   ```

2. **Monitor disk space**:
   ```bash
   # Check disk usage
   df -h .
   
   # Check large files
   du -sh * | sort -hr
   ```

3. **Check logs** for detailed error information:
   ```bash
   tail -f logs/instapost.log
   ```

## 🔍 Verifying App Permissions

### Dropbox Permissions
1. **Go to Dropbox App Console**:
   - Visit: https://www.dropbox.com/developers/apps
   - Select your app from the list

2. **Check OAuth 2 Settings**:
   - Under "OAuth 2" section, verify these scopes are enabled:
     - `files.content.write` (required for uploading files)
     - `sharing.write` (required for creating shared links)
     - `account_info.read` (required for basic account info)

3. **Check Access Token Permissions**:
   - Go to: https://www.dropbox.com/account/connected_apps
   - Find your app and click "View permissions"
   - Ensure all required permissions are granted

4. **Regenerate Token if Needed**:
   - If permissions are incorrect, you'll need to:
     1. Revoke the token in Dropbox account settings
     2. Delete the local `db_token.json` file
     3. Re-run the setup process

### Facebook Developer Portal Permissions
1. **Go to Facebook Developer Portal**:
   - Visit: https://developers.facebook.com/apps/
   - Select your app

2. **Check App Review Status**:
   - In the left sidebar, click "App Review"
   - Ensure your app is in "Live" mode (not Development mode)
   - Verify all required permissions are approved (with green checkmarks)

3. **Verify Required Permissions**:
   - Go to "App Settings" > "Advanced"
   - Under "App Review for Live Apps", ensure these permissions are approved:
     - `instagram_basic`
     - `instagram_content_publish`
     - `pages_show_list`
     - `pages_read_engagement`

4. **Check Token Permissions**:
   - Go to: https://developers.facebook.com/tools/debug/accesstoken/
   - Paste your access token and click "Debug"
   - Verify all required permissions are listed under "Permissions"
   - Check the token expiration date

5. **Check Instagram Account Connection**:
   - Go to: https://business.facebook.com/settings/instagram-api
   - Ensure your Instagram Business Account is connected
   - Verify the correct Facebook Page is linked

## 🔒 Security Best Practices

### Running as Non-Root
Never run the application as root. Instead:
```bash
# Create a dedicated user
sudo useradd -r -s /sbin/nologin instapost

# Set ownership of application files
sudo chown -R instapost:instapost /path/to/instapost

# Run as the dedicated user
sudo -u instapost python -m instapost.daemons.watcher
```

### Securing Sensitive Files
```bash
# Set restrictive permissions on sensitive files
chmod 600 .env db_token.json
chmod 700 logs

# Verify permissions
ls -la .env db_token.json
```

### API Security
- Rotate API tokens every 90 days
- Use the principle of least privilege for API permissions
- Monitor API usage for suspicious activity

## 📊 Monitoring & Maintenance

### Log Monitoring
```bash
# Follow the main log in real-time
tail -f logs/instapost.log

# Search for errors in logs
grep -i error logs/instapost.log

# Get statistics on processed files
jq '. | length' processed.json  # Total processed
jq '.[] | select(.status == "success")' processed.json | wc -l  # Successful posts
jq '.[] | select(.status == "failed")' processed.json | wc -l  # Failed posts
```

### System Resource Monitoring
```bash
# Monitor CPU/Memory usage
top -b -n 1 | grep python

# Check disk usage
df -h .

# Check inode usage
df -i .
```

## 🔄 Backup & Recovery

### Regular Backups
```bash
# Create a backup of critical files
BACKUP_DIR=~/instapost_backup_$(date +%Y%m%d)
mkdir -p $BACKUP_DIR
cp .env schedule.json processed.json db_token.json $BACKUP_DIR/

# Create a compressed archive
tar -czf instapost_backup_$(date +%Y%m%d).tar.gz $BACKUP_DIR
```

### Disaster Recovery
1. **Restore from backup**:
   ```bash
   tar -xzf instapost_backup_YYYYMMDD.tar.gz
   cp -i instapost_backup_YYYYMMDD/* ./
   ```

2. **Recovery after failure**:
   - Check logs: `tail -n 100 logs/instapost.log`
   - Verify API tokens are still valid
   - Check disk space and permissions

## 🧪 Testing Your Setup

### Dry Run Mode
```bash
# Run in test mode (processes one image immediately)
TEST_MODE=true python -m instapost.daemons.watcher ./images
TEST_MODE=true python -m instapost.daemons.scheduler
```

### Verify Configuration
```bash
# Check environment variables are set
env | grep -E 'DROPBOX|FACEBOOK|INSTAGRAM|LOG_'

# Test API connectivity
curl -s -o /dev/null -w "%{http_code}" "https://graph.facebook.com/v18.0/me/accounts?access_token=$FACEBOOK_ACCESS_TOKEN"
```

## 📈 Performance Considerations

### Handling Large Volumes
- Process up to 1,000 images per day within API limits
- Each image takes approximately 10-30 seconds to process
- Monitor API rate limits in the Facebook Developer Portal

### Resource Requirements
- **CPU**: Minimal (single core is sufficient)
- **Memory**: ~100MB base + ~50MB per concurrent upload
- **Disk**: 1GB free space recommended for logs and temporary files

### Scaling Tips
1. For high volume (>100 images/day):
   - Implement a queue system
   - Consider rate limiting
   - Monitor API quotas

2. For large files:
   - Pre-optimize images before adding to `images/`
   - Use appropriate image dimensions (1080x1080px recommended)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
