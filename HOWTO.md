# InstaPost - Instagram Posting Automation Tool

InstaPost is an automated workflow for scheduling and posting images to Instagram. It combines several components to create a seamless pipeline from image preparation to posting, with support for scheduling and automatic file management.

## Core Workflow

InstaPost's automation workflow consists of three main components that work together:

1. **Watcher** (`watcher.py`)
   - Monitors a specified directory for new image files
   - Automatically copies new images to the `images` directory
   - Adds new images to the posting schedule with full file paths
   - Supports common image formats: JPG, PNG, GIF, BMP, WebP
   - Updates `schedule.json` with new files and their posting times

2. **Scheduler** (`scheduler.py`)
   - Processes the posting schedule from `schedule.json`
   - Uses full file paths for reliable file access
   - Handles the posting workflow:
     1. Locates the image using the stored path
     2. Uploads the image to Dropbox
     3. Posts to Instagram using the Facebook Graph API
     4. Records successful posts in `processed.json`
   - Includes comprehensive error handling and logging
   - Runs continuously, checking for scheduled posts

3. **Mover** (`mover.py`)
   - Monitors the `processed.json` file
   - Moves successfully posted images to a processed directory
   - Helps keep the source directory clean and organized
   - Maintains file organization by date

## Package Structure

### Core Files

1. **`instapost/__init__.py`**
   - Package initializer file (currently empty)

2. **`instapost/cli.py`**
   - Command-line interface for interacting with the package
   - Main commands:
     - `post`: Upload and post an image to Instagram
     - `account-info`: Get Instagram account information
     - `recent-media`: View recent Instagram posts
     - `token-info`: Check Facebook token status
     - `setup-dropbox`: Configure Dropbox authentication

3. **`instapost/config.py`**
   - Handles configuration management
   - Defines Pydantic models for configuration
   - Loads settings from environment variables or .env file
   - Validates Facebook access tokens

### Dropbox Integration

4. **`instapost/dropbox/client.py`**
   - `DropboxClient` class for interacting with Dropbox API
   - Handles file uploads and generates public links
   - Manages authentication with refresh tokens

### Instagram Integration

5. **`instapost/instagram/client.py`**
   - `InstagramClient` class for Instagram Graph API interactions
   - Handles media container creation and publishing
   - Manages Instagram business account operations

### Facebook Integration

6. **`instapost/facebook/token.py`**
   - `FacebookToken` class for token management
   - Validates tokens and checks expiration
   - Retrieves token metadata

### Utility Files

7. **`instapost/utils.py`**
   - Common utility functions used throughout the package

8. **`instapost/image.py`**
   - Image processing utilities

9. **`instapost/post.py`**
   - Core posting functionality

10. **`instapost/scheduler.py`**
    - Core scheduling functionality
    - Manages the posting queue from `schedule.json`
    - Coordinates Dropbox uploads and Instagram posts

11. **`instapost/watcher.py`**
    - Monitors directories for new images
    - Automatically schedules new files for posting

12. **`instapost/mover.py`**
    - Manages file organization
    - Moves processed files to archive directories

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/instapost.git
   cd instapost
   ```

2. Install the package in development mode:
   ```bash
   pip install -e .
   ```

3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

## Configuration

1. Create a `.env` file in the project root with the following variables:
   ```
   # Dropbox API credentials
   DROPBOX_APP_KEY=your_dropbox_app_key
   DROPBOX_APP_SECRET=your_dropbox_app_secret
   DROPBOX_REFRESH_TOKEN=your_dropbox_refresh_token

   # Facebook Graph API credentials
   FACEBOOK_APP_ID=your_facebook_app_id
   FACEBOOK_APP_SECRET=your_facebook_app_secret
   FACEBOOK_ACCESS_TOKEN=your_facebook_access_token
   INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_account_id

   # Optional configuration
   DROPBOX_FOLDER_PATH=/INPOST333
   ```

## Running the Automation

### 1. Start the Watcher
From the project root directory, run:
```bash
python -m instapost.watcher images
```
- Monitors the `images` directory for new images
- Automatically adds them to the schedule with a 10-second delay

### 2. Start the Scheduler
```bash
python -m instapost.scheduler
```
- Processes scheduled posts
- Uploads to Dropbox and posts to Instagram
- Updates `schedule.json` and `processed.json`

### 3. Start the Mover (Optional)
From the project root directory, run:
```bash
python -m instapost.mover images processed
```
- Moves processed files from `images` to `processed` directory
- Only moves files that were successfully posted

## Troubleshooting

### Common Issues

1. **File Not Found Errors**
   - Ensure the watcher has copied files to the `images` directory
   - Check that `original_path` in `schedule.json` points to a valid file
   - Verify file permissions in the watched directories

2. **Instagram Posting Failures**
   - Check Facebook Graph API token validity
   - Verify Instagram Business Account is properly connected
   - Ensure the image meets Instagram's requirements

3. **Dropbox Upload Issues**
   - Verify Dropbox refresh token is valid
   - Check available storage space
   - Ensure proper permissions are set

### Logs and Debugging

- Enable verbose logging by setting `VERBOSE=1` in the environment
- Check the console output for error messages
- Look for detailed error information in the logs

### Resetting the System

To start fresh:
1. Stop all running processes
2. Backup and clear `schedule.json` and `processed.json`
3. Restart the watcher and scheduler

## Manual Usage

### Post an Image

```bash
instapost post path/to/your/image.jpg --caption "Your caption here"
```

### Get Instagram Account Info

```bash
instapost account-info
```

### View Recent Instagram Posts

```bash
instapost recent-media --limit 5
```

### Check Facebook Token Status

```bash
instapost token-info
```

### Set Up Dropbox Authentication

```bash
instapost setup-dropbox
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
```

### Type Checking

```bash
mypy instapost
```

## Dependencies

- Python 3.13+
- dropbox
- python-dotenv
- requests
- pydantic
- click
- python-dateutil

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
