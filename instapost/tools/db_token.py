import os
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
import argparse
import time


def load_env(file_path=None):
    if file_path is None:
        # Look for .env in the project root (one level up from instapost/)
        file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    """Load key-value pairs from .env file into os.environ."""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"Error: .env file not found at {file_path}")
        exit(1)
    except Exception as e:
        print(f"Error loading .env: {e}")
        exit(1)


def format_expiration(expires_at):
    """Format expiration timestamp to readable string."""
    if expires_at == 0:
        return "Never expires"
    else:
        exp_time = datetime.fromtimestamp(expires_at)
        return exp_time.strftime("%Y-%m-%d %H:%M:%S")


def store_token(access_token, expires_in, scopes, uid, account_id):
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


def validate_access_token(access_token):
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
        if e.code == 401:
            return None  # Expired or invalid
        else:
            print(f"HTTP Error during validation: {e.code} - {e.reason}")
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                print("Error Details:", json.dumps(error_data, indent=2))
            except:
                pass
            return None
    except Exception as e:
        print(f"Unexpected Error during validation: {e}")
        return None


def refresh_access_token():
    """Refresh the access token using refresh token."""
    app_key = os.environ.get('DROPBOX_APP_KEY')
    app_secret = os.environ.get('DROPBOX_APP_SECRET')
    refresh_token = os.environ.get('DROPBOX_REFRESH_TOKEN')

    if not all([app_key, app_secret, refresh_token]):
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
            print("Error: No access_token in refresh response.")
            return None, None, None, None, None

        expires_in = refresh_info.get('expires_in', 0)
        scopes = refresh_info.get('scope', '')
        uid = refresh_info.get('uid')
        account_id = refresh_info.get('account_id')

        return access_token, expires_in, scopes, uid, account_id
    except urllib.error.HTTPError as e:
        print(f"HTTP Error during refresh: {e.code} - {e.reason}")
        try:
            error_data = json.loads(e.read().decode('utf-8'))
            print("Error Details:", json.dumps(error_data, indent=2))
        except:
            pass
        return None, None, None, None, None
    except Exception as e:
        print(f"Unexpected Error during refresh: {e}")
        return None, None, None, None, None


def check_dropbox_token():
    """Check validity and properties of Dropbox refresh token, reusing stored access token if possible."""
    # Try to load stored token
    stored_data = load_stored_token()
    reused = False
    if stored_data:
        account_info = validate_access_token(stored_data['access_token'])
        if account_info:
            print("Reused stored access token (valid).")
            reused = True
            access_token = stored_data['access_token']
            expires_at = stored_data['expires_at']
            scopes = stored_data['scopes']
            uid = stored_data['uid']
            account_id = stored_data['account_id']
        else:
            print("Stored access token invalid/expired; refreshing...")

    if not reused:
        access_token, expires_in, scopes, uid, account_id = refresh_access_token()
        if not access_token:
            print("Refresh token is invalid.")
            return

        expires_at = time.time() + expires_in
        store_token(access_token, expires_in, scopes, uid, account_id)

        account_info = validate_access_token(access_token)
        if not account_info:
            print("New access token validation failed.")
            return

        print("Refresh token is valid.")
        print("Refresh Token Expiration: Never expires (unless revoked)")

        print(f"New Access Token Expiration: {format_expiration(expires_at)}")

        if scopes:
            print("Scopes:", scopes)
        else:
            print("Scopes: None")

        if uid:
            print(f"UID: {uid}")

        if account_id:
            print(f"Account ID: {account_id}")

        print("\nNew Access Token:")
        print(access_token)
    else:
        # For reused token
        print("Refresh Token Expiration: Never expires (unless revoked)")  # Assuming valid if access is valid
        print(f"Access Token Expiration: {format_expiration(expires_at)}")

        if scopes:
            print("Scopes:", scopes)
        else:
            print("Scopes: None")

        if uid:
            print(f"UID: {uid}")

        if account_id:
            print(f"Account ID: {account_id}")

        print("\nReused Access Token:")
        print(access_token)

    print("\nAccess Token Validation: Successful")
    print("\nAccount Properties:")
    for key, value in account_info.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Dropbox Token Utility Script.

        This script checks the validity and properties of a Dropbox refresh token 
        stored in ../.env by attempting to refresh it and obtain a new access token if necessary.
        It reuses a valid stored access token from db_token.json when possible.
        It then validates the access token by fetching account information.

        Ensure your ../.env file contains:
        DROPBOX_APP_KEY=your_app_key
        DROPBOX_APP_SECRET=your_app_secret
        DROPBOX_REFRESH_TOKEN=your_refresh_token

        Run example:
        - To check and refresh if needed: python db_token.py --check
        (If successful, it will print the access token and account details.)
        """
    )
    parser.add_argument('--check', action='store_true', help='Check and refresh the token stored in .env if needed')

    args = parser.parse_args()

    # Load .env
    load_env()

    if args.check:
        check_dropbox_token()
    else:
        parser.print_help()