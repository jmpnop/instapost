# InstaPost

A command-line tool for automating the scheduling and posting of images to Instagram using Facebook Graph API and Dropbox.

## Features

- **Automated Scheduling**: Monitor directories and automatically schedule posts
- **Reliable Uploads**: Upload images to Dropbox with automatic link generation
- **Instagram Integration**: Post images to Instagram using Facebook Graph API
- **Robust Error Handling**: Comprehensive logging and error recovery
- **Flexible Configuration**: Customize settings via environment variables
- **File Management**: Automatic organization of processed files
- **Account Management**: View account info and recent posts
- **Token Validation**: Check and validate Facebook access tokens

## Automation Features

InstaPost provides a powerful automation system for scheduling and managing Instagram posts:

- **Directory Monitoring**: Automatically detect and process new images in watched directories
- **Flexible Scheduling**: Schedule posts for specific times or use default intervals
- **Reliable Processing**: Built-in retry logic and error handling
- **Comprehensive Logging**: Detailed logs for troubleshooting and monitoring
- **File Management**: Automatic organization of processed and scheduled files

## Installation

### Prerequisites

- Python 3.13 or higher
- Dropbox API app with appropriate permissions
- Facebook Developer account with Instagram Graph API access
- Instagram Business or Creator account connected to a Facebook Page

### Install from source

```bash
git clone https://github.com/yourusername/instapost.git
cd instapost
pip install -e .
```

## Configuration

1. Create a `.env` file in your project directory based on the provided `.env.example`:

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

### Setting up Dropbox API

1. Go to the [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2. Create a new app with the following settings:
   - API: Dropbox API
   - Access type: Full Dropbox
   - Permissions: files.content.write, files.content.read, sharing.write
3. Note your App Key and App Secret
4. Run the setup command to get your refresh token:

```bash
instapost setup-dropbox
```

5. Follow the instructions to authorize the app and get your refresh token
6. Add the refresh token to your `.env` file

### Setting up Facebook Graph API

1. Go to the [Facebook Developer Console](https://developers.facebook.com/)
2. Create a new app with the "Business" type
3. Add the "Instagram Graph API" product to your app
4. Connect your Instagram Business account to your Facebook Page
5. Generate a long-lived access token with the following permissions:
   - instagram_basic
   - instagram_content_publish
   - pages_read_engagement
6. Find your Instagram Business Account ID using the [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
7. Add all credentials to your `.env` file

## Usage

### Posting an Image to Instagram

```bash
instapost post /path/to/your/image.jpg --caption "Your caption here"
```

This command will:
1. Upload the image to Dropbox
2. Generate a public link with `raw=1` parameter
3. Post the image to Instagram with the provided caption

### Getting Account Information

```bash
instapost account-info
```

### Viewing Recent Media

```bash
instapost recent-media --limit 10
```

### Checking Facebook Token Information

```bash
instapost token-info
```

This command will:
1. Validate your Facebook access token
2. Check if the token is expired or about to expire
3. Display token properties including:
   - Expiration date
   - Scopes (permissions)
   - User ID
   - App ID
   - Token type

### Using a Custom .env File

```bash
instapost --env-file /path/to/your/.env post /path/to/your/image.jpg --caption "Your caption here"
```

## Development

### Setting up a development environment

```bash
git clone https://github.com/yourusername/instapost.git
cd instapost
pip install -e ".[dev]"
```

### Running tests

```bash
pytest
```

## License

MIT

## Acknowledgements

- [Dropbox API](https://www.dropbox.com/developers/documentation/http/overview)
- [Facebook Graph API](https://developers.facebook.com/docs/graph-api)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)