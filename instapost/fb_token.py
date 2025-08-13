import os
import urllib.request
import json
from datetime import datetime, timezone
import argparse


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


def format_timestamp(ts):
    """Convert Unix timestamp to readable UTC date string. Returns 'Never expires' if 0."""
    if ts == 0:
        return "Never expires"
    else:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def check_facebook_token():
    """Check validity, expiration, and properties of Facebook access token from .env."""
    app_id = os.environ.get('FACEBOOK_APP_ID')
    app_secret = os.environ.get('FACEBOOK_APP_SECRET')
    access_token = os.environ.get('FACEBOOK_ACCESS_TOKEN')

    if not all([app_id, app_secret, access_token]):
        print(
            "Error: Missing required environment variables (FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, FACEBOOK_ACCESS_TOKEN)")
        return

    app_token = f"{app_id}|{app_secret}"
    url = f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={app_token}"

    try:
        with urllib.request.urlopen(url) as response:
            raw_data = response.read().decode('utf-8')
            data = json.loads(raw_data)

        if 'data' in data:
            token_data = data['data']
            if 'is_valid' in token_data:
                if token_data['is_valid']:
                    print("Token is valid.")

                    expires_at = token_data.get('expires_at', 0)
                    print(f"Expiration: {format_timestamp(expires_at)}")

                    scopes = token_data.get('scopes', [])
                    if scopes:
                        print("Scopes:", ', '.join(scopes))
                    else:
                        print("Scopes: None")

                    # Handle specific timestamp fields with conversion
                    issued_at = token_data.get('issued_at', 0)
                    if issued_at:
                        print(f"Issued At: {format_timestamp(issued_at)}")

                    data_access_expires_at = token_data.get('data_access_expires_at', 0)
                    if data_access_expires_at:
                        print(f"Data Access Expires At: {format_timestamp(data_access_expires_at)}")

                    # Print remaining additional properties
                    print("\nAdditional Properties:")
                    excluded_keys = ['is_valid', 'expires_at', 'scopes', 'issued_at', 'data_access_expires_at']
                    additional_props = {k: v for k, v in token_data.items() if k not in excluded_keys}
                    if additional_props:
                        for key, value in additional_props.items():
                            print(f"{key}: {value}")
                    else:
                        print("None")
                else:
                    print("Token is invalid.")
            else:
                print("Error: 'is_valid' not found in response data.")
        else:
            error = data.get('error', {})
            print("Error:", error.get('message', 'Unknown error'))
            print("Error Type:", error.get('type', 'N/A'))
            print("Error Code:", error.get('code', 'N/A'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        try:
            error_data = json.loads(e.read().decode())
            print("Error Details:", error_data.get('error', 'No details'))
        except:
            pass
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
    except json.JSONDecodeError:
        print("Error: Invalid JSON response from API.")
    except Exception as e:
        print(f"Unexpected Error: {e}")


def exchange_for_long_lived(short_lived_token):
    """Exchange a short-lived token for a long-lived one using app credentials from .env."""
    app_id = os.environ.get('FACEBOOK_APP_ID')
    app_secret = os.environ.get('FACEBOOK_APP_SECRET')

    if not all([app_id, app_secret]):
        print("Error: Missing required environment variables (FACEBOOK_APP_ID, FACEBOOK_APP_SECRET)")
        return None

    url = (
        f"https://graph.facebook.com/v20.0/oauth/access_token?"
        f"grant_type=fb_exchange_token&"
        f"client_id={app_id}&"
        f"client_secret={app_secret}&"
        f"fb_exchange_token={short_lived_token}"
    )
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode('utf-8'))
            long_lived_token = data.get('access_token')
            if long_lived_token:
                print("Successfully obtained long-lived token.")
                return long_lived_token
            else:
                print("Error: No access_token in response.")
                return None
    except urllib.error.HTTPError as e:
        print(f"HTTP Error during exchange: {e.code} - {e.reason}")
        try:
            error_data = json.loads(e.read().decode())
            print("Error Details:", error_data.get('error', 'No details'))
        except:
            pass
        return None
    except Exception as e:
        print(f"Unexpected Error during exchange: {e}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Facebook Token Utility Script.

        This script can check the validity and properties of a Meta Graph API access token 
        stored in ../.env, or exchange a short-lived token for a long-lived one.

        Ensure your ../.env file contains:
        FACEBOOK_APP_ID=your_app_id
        FACEBOOK_APP_SECRET=your_app_secret
        (And optionally FACEBOOK_ACCESS_TOKEN=your_token for checking)

        Run examples:
        - To check token: python check_fb.py --check
        - To exchange: python check_fb.py --exchange YOUR_SHORT_LIVED_TOKEN
        (After exchange, copy the printed long-lived token and update .env if needed.)
        """
    )
    parser.add_argument('--check', action='store_true', help='Check the token stored in .env')
    parser.add_argument('--exchange', type=str, help='Short-lived token to exchange for long-lived')

    args = parser.parse_args()

    # Load .env always, as needed for app credentials
    load_env()

    if args.exchange:
        long_lived = exchange_for_long_lived(args.exchange)
        if long_lived:
            print("\nLong-lived token:")
            print(long_lived)
            print("\nUpdate your .env with FACEBOOK_ACCESS_TOKEN=" + long_lived)
            # Optionally check the new token
            os.environ['FACEBOOK_ACCESS_TOKEN'] = long_lived
            print("\nChecking the new long-lived token:")
            check_facebook_token()
    elif args.check:
        check_facebook_token()
    else:
        parser.print_help()