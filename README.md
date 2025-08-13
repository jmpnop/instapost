# InstaPost - Instagram Posting Automation

A command-line tool for automating the scheduling and posting of images to Instagram using Facebook Graph API and Dropbox.

## Features

- **Automated Posting**: Schedule and post images to Instagram automatically
- **Directory Monitoring**: Watch folders for new images and add them to the posting queue
- **Flexible Scheduling**: Configure custom posting times with a weekly schedule
- **Test Mode**: Validate your setup with immediate post processing
- **Cloud Integration**: Seamless Dropbox uploads with automatic link generation
- **Process Safety**: Built-in protection against multiple instances
- **Comprehensive Logging**: Detailed logs for monitoring and troubleshooting
- **Automatic Organization**: Move processed files to dated directories

## Core Components

### 1. Watcher (`watcher.py`)
- Monitors specified directories for new images
- Validates image files (JPG, PNG only)
- Maintains schedule in `schedule.json`
- Implements process safety to prevent multiple instances
- Shows idle animation when waiting for changes

### 2. Scheduler (`scheduler.py`)
- Processes scheduled posts according to `WEEKLY_SCHEDULE`
- **Production Mode** (default): Follows the weekly schedule
- **Test Mode**: When `TEST_MODE=true` environment variable is set, processes all posts immediately
- Handles complete posting workflow:
  1. Validates scheduled times
  2. Processes images through Dropbox upload
  3. Posts to Instagram via Facebook Graph API
  4. Updates `processed.json`

### 3. Mover (`mover.py`)
- Monitors `processed.json` for completed posts
- Organizes processed files into dated directories
- Keeps working directory clean

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

2. **Create and activate a virtual environment** (recommended):
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. **Install the package in development mode**:
   ```bash
   uv pip install -e .
   ```

4. **Create required directories**:
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
python -m instapost.cli setup-dropbox
```

5. Follow the instructions to authorize the app and get your refresh token
6. Add the refresh token to your `.env` file
7. Navigate to the folder in Dropbox that will store your images. Copy its full path exactly as shown in Dropbox (e.g. /InstagramPosts or /Apps/InstaPost/images).
8. Add the DROPBOX_FOLDER_PATH  to your `.env` file

### Setting up Facebook Graph API

1. Go to the [Facebook Developer Console](https://developers.facebook.com/)
2. Create a new app with the "Business" type
3. Add the "Instagram Graph API" product to your app
4. Connect your Instagram Business account to your Facebook Page
5. In the App Dashboard → Settings → Basic, copy your:
   FACEBOOK_APP_ID
   FACEBOOK_APP_SECRET
6. Go to Tools → Access Token Tool. Generate a short-lived access token with the following permissions:
   - instagram_basic
   - instagram_content_publish
   - pages_read_engagement
7. Exchange it for a long-lived token using: 
```bash
curl -X GET \
"https://graph.facebook.com/v18.0/oauth/access_token?  
 grant_type=fb_exchange_token&  
 client_id=FACEBOOK_APP_ID&  
 client_secret=FACEBOOK_APP_SECRET&  
 fb_exchange_token=SHORT_LIVED_TOKEN"
The response will contain your long-term FACEBOOK_ACCESS_TOKEN
```
8. Find your INSTAGRAM_BUSINESS_ACCOUNT_ID using the [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
9. Add all credentials to your `.env` file

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Dropbox Configuration
# 1. Get these from your Dropbox App at https://www.dropbox.com/developers/apps
DROPBOX_APP_KEY=your_dropbox_app_key         # From Dropbox App Console -> App Key
DROPBOX_APP_SECRET=your_dropbox_app_secret   # From Dropbox App Console -> App Secret
# 2. Get this by running: python -m instapost.cli setup-dropbox
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

### Start the Watcher
```bash
python -m instapost.watcher /path/to/images
```

### Start the Scheduler
```bash
# Production mode (follows schedule)
python -m instapost.scheduler

# Test mode (process immediately)
TEST_MODE=true python -m instapost.scheduler
```
> **Note:** `TEST_MODE` only affects the scheduler. The watcher operates the same way in both modes.

### Start the Mover
```bash
python -m instapost.mover
```
> The mover runs continuously, moving processed files to their respective dated directories in the `processed/` folder.

### Check Account Info
```bash
python -m instapost.cli account-info
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

1. **Token Issues**
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
     ps aux | grep "python -m instapost"
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

2. **Start all services** (in separate terminal windows):
   ```bash
   # Terminal 1 - Watcher
   python -m instapost.watcher ./images
   
   # Terminal 2 - Scheduler
   python -m instapost.scheduler
   
   # Terminal 3 - Mover
   python -m instapost.mover
   ```

3. **Add images to monitor**:
   ```bash
   # Copy images to the watched directory
   cp your_images/*.jpg ./images/
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
   ps aux | grep "python -m instapost"
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
sudo -u instapost python -m instapost.watcher
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
TEST_MODE=true python -m instapost.watcher ./images
TEST_MODE=true python -m instapost.scheduler
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
