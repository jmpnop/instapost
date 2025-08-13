import os
import urllib.request
import urllib.parse
import json
import argparse
import time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import sys


def load_env(file_path=None, verbose=False):
    """Load key-value pairs from .env file into os.environ."""
    if file_path is None:
        # Look for .env in the project root (one level up from instapost/)
        file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    
    try:
        if verbose:
            print(f"Loading environment from: {os.path.abspath(file_path)}")
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key and value:
                            os.environ[key] = value
                            if verbose:
                                if any(secret in key.upper() for secret in ['TOKEN', 'SECRET', 'KEY', 'PASSWORD']):
                                    print(f"Loaded {key}=[REDACTED]")
                                else:
                                    print(f"Loaded {key}={value}")
    except Exception as e:
        print(f"Error loading .env from {file_path}: {e}")
        return False
    return True


def format_expiration(expires_at):
    """Format expiration timestamp to readable string."""
    if expires_at == 0:
        return "Never expires"
    else:
        exp_time = datetime.fromtimestamp(expires_at)
        return exp_time.strftime("%Y-%m-%d %H:%M:%S")


def store_token(access_token, expires_in, scopes, uid, account_id, verbose=False):
    """Store access token, expiration, and additional info in db_token.json."""
    from .utils import PROJECT_ROOT
    expires_at = time.time() + expires_in
    token_data = {
        "access_token": access_token,
        "expires_at": expires_at,
        "scopes": scopes,
        "uid": uid,
        "account_id": account_id
    }
    token_file = PROJECT_ROOT / 'db_token.json'
    with open(token_file, 'w') as f:
        json.dump(token_data, f)
    if verbose:
        print(f"Stored new access token and info in {token_file}")


def load_stored_token():
    """Load stored access token and info if valid."""
    from .utils import PROJECT_ROOT
    token_file = PROJECT_ROOT / 'db_token.json'
    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        access_token = token_data.get('access_token')
        expires_at = token_data.get('expires_at', 0)
        if access_token and time.time() < expires_at - 300:  # 5 min buffer
            return {
                "access_token": access_token,
                "expires_at": expires_at,
                "scopes": token_data.get('scopes'),
                "uid": token_data.get('uid'),
                "account_id": token_data.get('account_id')
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return None


def validate_access_token(access_token, verbose=False):
    """Validate access token by calling get_current_account."""
    account_url = "https://api.dropboxapi.com/2/users/get_current_account"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    account_req = urllib.request.Request(account_url, data=b'null', headers=headers, method='POST')

    try:
        with urllib.request.urlopen(account_req) as account_response:
            account_raw = account_response.read().decode('utf-8')
            account_info = json.loads(account_raw)
        return account_info
    except urllib.error.HTTPError as e:
        if verbose:
            if e.code == 401:
                print("Access token expired or invalid.")
            else:
                print(f"HTTP Error during validation: {e.code} - {e.reason}")
                try:
                    error_data = json.loads(e.read().decode('utf-8'))
                    print("Error Details:", json.dumps(error_data, indent=2))
                except:
                    pass
        return None
    except Exception as e:
        if verbose:
            print(f"Unexpected Error during validation: {e}")
        return None


def refresh_access_token(verbose=False):
    """Refresh the access token using refresh token."""
    app_key = os.environ.get('DROPBOX_APP_KEY')
    app_secret = os.environ.get('DROPBOX_APP_SECRET')
    refresh_token = os.environ.get('DROPBOX_REFRESH_TOKEN')

    if not all([app_key, app_secret, refresh_token]):
        if verbose:
            print(
                "Error: Missing required environment variables (DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN)")
        return None, None, None, None, None

    refresh_url = "https://api.dropboxapi.com/oauth2/token"
    refresh_params = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': app_key,
        'client_secret': app_secret
    }
    refresh_data = urllib.parse.urlencode(refresh_params).encode('utf-8')

    try:
        refresh_req = urllib.request.Request(refresh_url, data=refresh_data, method='POST')
        with urllib.request.urlopen(refresh_req) as response:
            refresh_raw = response.read().decode('utf-8')
            refresh_info = json.loads(refresh_raw)

        access_token = refresh_info.get('access_token')
        if not access_token:
            if verbose:
                print("Error: No access_token in refresh response.")
            return None, None, None, None, None

        expires_in = refresh_info.get('expires_in', 0)
        scopes = refresh_info.get('scope', '')
        uid = refresh_info.get('uid')
        account_id = refresh_info.get('account_id')

        return access_token, expires_in, scopes, uid, account_id
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"HTTP Error during refresh: {e.code} - {e.reason}")
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                print("Error Details:", json.dumps(error_data, indent=2))
            except:
                pass
        return None, None, None, None, None
    except Exception as e:
        if verbose:
            print(f"Unexpected Error during refresh: {e}")
        return None, None, None, None, None


def refresh_token_if_needed(verbose=False):
    """Refresh token if expired or missing."""
    stored_data = load_stored_token()
    if stored_data:
        account_info = validate_access_token(stored_data['access_token'], verbose)
        if account_info:
            if verbose:
                print("Reused stored access token (valid).")
            return stored_data['access_token']
        else:
            if verbose:
                print("Stored access token invalid/expired; refreshing...")

    access_token, expires_in, scopes, uid, account_id = refresh_access_token(verbose)
    if not access_token:
        if verbose:
            print("Refresh token is invalid.")
        return None

    store_token(access_token, expires_in, scopes, uid, account_id, verbose)

    account_info = validate_access_token(access_token, verbose)
    if not account_info:
        if verbose:
            print("New access token validation failed.")
        return None

    if verbose:
        print("Refresh successful.")
    return access_token


def generate_noise_image(verbose=False):
    """Generate a temporary image with noise and timestamp text."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    noise = np.random.rand(200, 200, 3)  # Simple RGB noise image
    fig, ax = plt.subplots()
    ax.imshow(noise)
    ax.text(10, 20, timestamp, color='white', fontsize=12, bbox=dict(facecolor='black', alpha=0.5))
    ax.axis('off')
    temp_file = 'temp_noise_image.png'
    plt.savefig(temp_file, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    if verbose:
        print(f"Generated temporary image: {temp_file}")
    return temp_file


def upload_image_to_dropbox(access_token, file_path, verbose=False):
    """Upload image to Dropbox and return the path."""
    if not os.path.exists(file_path):
        if verbose:
            print(f"Error: File not found at {file_path}")
        return None

    filename = os.path.basename(file_path)
    folder_path = os.environ.get('DROPBOX_FOLDER_PATH', '/')
    dropbox_path = f"{folder_path.rstrip('/')}/{filename}"

    upload_url = "https://content.dropboxapi.com/2/files/upload"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Dropbox-API-Arg': json.dumps({
            "path": dropbox_path,
            "mode": "add",
            "autorename": True,
            "mute": False,
            "strict_conflict": False
        }),
        'Content-Type': 'application/octet-stream'
    }

    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        req = urllib.request.Request(upload_url, data=file_data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            response_data = json.loads(response.read().decode('utf-8'))
        if verbose:
            print("Upload successful.")
        return response_data['path_lower']
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"HTTP Error during upload: {e.code} - {e.reason}")
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                print("Error Details:", json.dumps(error_data, indent=2))
            except:
                pass
        return None
    except Exception as e:
        if verbose:
            print(f"Unexpected Error during upload: {e}")
        return None


def create_shared_link(access_token, dropbox_path, verbose=False):
    """Create a shared link for the uploaded file."""
    share_url = "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    body = json.dumps({
        "path": dropbox_path,
        "settings": {
            "requested_visibility": "public",
            "audience": "public",
            "access": "viewer"
        }
    }).encode('utf-8')

    try:
        # First try to create a new shared link
        req = urllib.request.Request(share_url, data=body, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            response_data = json.loads(response.read().decode('utf-8'))
        shared_link = response_data['url']
        # Modify to raw=1 for direct access, handling scl format
        raw_link = shared_link.replace('dl=0', 'raw=1')
        if verbose:
            print("Shared link created.")
        return raw_link
    except urllib.error.HTTPError as e:
        if e.code == 409:  # Shared link already exists
            if verbose:
                print("Shared link already exists, fetching existing link...")
            # Try to get existing shared links
            list_shared_links_url = "https://api.dropboxapi.com/2/sharing/list_shared_links"
            list_body = json.dumps({"path": dropbox_path, "direct_only": True}).encode('utf-8')
            req = urllib.request.Request(
                list_shared_links_url, 
                data=list_body, 
                headers=headers, 
                method='POST'
            )
            try:
                with urllib.request.urlopen(req) as response:
                    links_data = json.loads(response.read().decode('utf-8'))
                    if links_data.get('links') and len(links_data['links']) > 0:
                        shared_link = links_data['links'][0]['url']
                        raw_link = shared_link.replace('dl=0', 'raw=1')
                        if verbose:
                            print(f"Found existing shared link: {raw_link}")
                        return raw_link
            except Exception as list_error:
                if verbose:
                    print(f"Error listing shared links: {list_error}")
                return None
        
        if verbose:
            print(f"HTTP Error during share: {e.code} - {e.reason}")
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                print("Error Details:", json.dumps(error_data, indent=2))
            except:
                pass
        return None
    except Exception as e:
        if verbose:
            print(f"Unexpected Error during share: {e}")
        return None


# Load environment variables at module level
load_env()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Dropbox Image Upload Utility.

        This script uploads an image to Dropbox, creates a shared link with ?raw=1,
        and prints it. If no --file is provided, generates a noise image with timestamp.
        It checks and refreshes the access token if needed.

        Ensure ../.env has DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN,
        and optionally DROPBOX_FOLDER_PATH (default '/').

        Run examples:
        python db_upload.py --file /path/to/image.jpg
        python db_upload.py  # Generates noise image
        """
    )
    parser.add_argument('--file', type=str, help='Path to the image file to upload (optional)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    # Load .env for credentials and folder path
    load_env()

    is_temp = False
    if not args.file:
        args.file = generate_noise_image(args.verbose)
        is_temp = True

    access_token = refresh_token_if_needed(args.verbose)
    if not access_token:
        if args.verbose:
            print("Failed to obtain valid access token.")
        if is_temp:
            os.remove(args.file)
        sys.exit(-1)

    dropbox_path = upload_image_to_dropbox(access_token, args.file, args.verbose)
    if not dropbox_path:
        if args.verbose:
            print("Upload failed.")
        if is_temp:
            os.remove(args.file)
        sys.exit(-1)

    raw_link = create_shared_link(access_token, dropbox_path, args.verbose)
    if raw_link:
        if not args.verbose:
            # In non-verbose mode, only print the raw link for the scheduler to capture
            print(raw_link)
        else:
            print("\nRaw Image URL for posting:")
            print(raw_link)
    else:
        if args.verbose:
            print("Failed to create shared link.")
        sys.exit(-1)

    if is_temp:
        os.remove(args.file)
        if args.verbose:
            print(f"Cleaned up temporary file: {args.file}")
    sys.exit(0)