import os
import urllib.request
import urllib.parse
import json
import argparse
import sys
import subprocess


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
        print(f"Error loading .env from {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def check_fb_token(verbose=False):
    """Check Meta token validity and properties."""
    app_id = os.environ.get('FACEBOOK_APP_ID')
    app_secret = os.environ.get('FACEBOOK_APP_SECRET')
    access_token = os.environ.get('FACEBOOK_ACCESS_TOKEN')

    if not all([app_id, app_secret, access_token]):
        if verbose:
            print(
                "Error: Missing required environment variables (FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, FACEBOOK_ACCESS_TOKEN)")
        return None

    app_token = f"{app_id}|{app_secret}"
    url = f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={app_token}"

    try:
        with urllib.request.urlopen(url) as response:
            raw_data = response.read().decode('utf-8')
            data = json.loads(raw_data)

        if 'data' in data:
            token_data = data['data']
            if token_data.get('is_valid'):
                if verbose:
                    print("Token is valid.")
                return access_token
            else:
                if verbose:
                    print("Token is invalid.")
                return None
        else:
            if verbose:
                error = data.get('error', {})
                print("Error:", error.get('message', 'Unknown error'))
            return None
    except Exception as e:
        if verbose:
            print(f"Unexpected Error: {e}")
        return None


def get_image_url(verbose=False):
    """Get image URL by calling db_upload.py."""
    result = subprocess.run(['python', 'db_upload.py'], capture_output=True, text=True)
    if result.returncode == 0:
        image_url = result.stdout.strip()
        if image_url:
            if verbose:
                print(f"Obtained image URL: {image_url}")
            return image_url
        else:
            if verbose:
                print("No image URL returned from db_upload.py.")
            return None
    else:
        if verbose:
            print("db_upload.py failed.")
            print(result.stdout)
            print(result.stderr)
        return None


def post_to_instagram(access_token, image_url, caption, ig_account_id, verbose=False):
    """Post image to Instagram via Meta Graph API."""
    if not all([access_token, image_url, ig_account_id]):
        error_msg = "Error: Missing required parameters. Ensure access_token, image_url, and ig_account_id are provided."
        if verbose:
            print(error_msg)
        return None, error_msg
        
    if verbose:
        print(f"\n=== Instagram Post Debug ===")
        print(f"Account ID: {ig_account_id}")
        print(f"Access Token: {access_token[:10]}...")
        print(f"Image URL: {image_url}")
        print(f"Caption: {caption}")

    # Step 1: Create media container
    create_url = f"https://graph.facebook.com/v20.0/{ig_account_id}/media"
    create_params = {
        'image_url': image_url,
        'caption': caption,
        'access_token': access_token
    }
    create_data = urllib.parse.urlencode(create_params).encode('utf-8')

    try:
        create_req = urllib.request.Request(create_url, data=create_data, method='POST')
        with urllib.request.urlopen(create_req) as response:
            create_info = json.loads(response.read().decode('utf-8'))
        container_id = create_info.get('id')
        if not container_id:
            error_msg = f"Error: No container ID returned. Response: {create_info}"
            if verbose:
                print(error_msg)
            return None, error_msg
        if verbose:
            print(f"Media container created: {container_id}")
    except urllib.error.HTTPError as e:
        error_details = {}
        try:
            error_data = e.read().decode('utf-8')
            error_details = json.loads(error_data) if error_data else {}
            if verbose:
                print(f"\n=== API Error Response ===")
                print(f"Status: {e.code} {e.reason}")
                print(f"Headers: {dict(e.headers)}")
                print(f"Response: {error_data}")
        except Exception as read_error:
            if verbose:
                print(f"Failed to read error details: {read_error}")
        
        error_msg = f"HTTP Error during create: {e.code} - {e.reason}"
        if 'error' in error_details:
            error_msg += f"\nError Type: {error_details.get('error', {}).get('type', 'Unknown')}"
            error_msg += f"\nError Code: {error_details.get('error', {}).get('code', 'Unknown')}"
            error_msg += f"\nMessage: {error_details.get('error', {}).get('message', 'No message')}"
            if 'error_subcode' in error_details.get('error', {}):
                error_msg += f"\nSubcode: {error_details['error']['error_subcode']}"
            if 'error_user_msg' in error_details.get('error', {}):
                error_msg += f"\nUser Message: {error_details['error']['error_user_msg']}"
        
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected Error during create: {str(e)}"
        if verbose:
            print(error_msg)
        return None, error_msg

    # Step 2: Publish the container
    publish_url = f"https://graph.facebook.com/v20.0/{ig_account_id}/media_publish"
    publish_params = {
        'creation_id': container_id,
        'access_token': access_token
    }
    publish_data = urllib.parse.urlencode(publish_params).encode('utf-8')

    try:
        publish_req = urllib.request.Request(publish_url, data=publish_data, method='POST')
        with urllib.request.urlopen(publish_req) as response:
            publish_info = json.loads(response.read().decode('utf-8'))
        post_id = publish_info.get('id')
        if post_id:
            if verbose:
                print("Post successful.")
            return post_id, None
        else:
            error_msg = f"Error: No post ID returned. Response: {publish_info}"
            if verbose:
                print(error_msg)
            return None, error_msg
    except urllib.error.HTTPError as e:
        error_msg = f"HTTP Error during publish: {e.code} - {e.reason}"
        if verbose:
            print(error_msg)
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                error_details = json.dumps(error_data, indent=2)
                print(f"Error Details: {error_details}")
                error_msg += f"\n{error_details}"
            except Exception as read_error:
                if verbose:
                    print(f"Failed to read error details: {read_error}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected Error during publish: {str(e)}"
        if verbose:
            print(error_msg)
        return None, error_msg


def get_instagram_permalink(access_token, post_id, verbose=False):
    """Fetch the permalink for the posted media."""
    permalink_url = f"https://graph.facebook.com/v20.0/{post_id}?fields=permalink&access_token={access_token}"

    try:
        with urllib.request.urlopen(permalink_url) as response:
            data = json.loads(response.read().decode('utf-8'))
        permalink = data.get('permalink')
        if permalink:
            if verbose:
                print(f"Permalink fetched: {permalink}")
            return permalink
        else:
            if verbose:
                print("Error: No permalink returned.")
            return None
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"HTTP Error during permalink fetch: {e.code} - {e.reason}")
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                print("Error Details:", json.dumps(error_data, indent=2))
            except:
                pass
        return None
    except Exception as e:
        if verbose:
            print(f"Unexpected Error during permalink fetch: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="""Instagram Post Utility.

        Either provide an image URL or let the script call db_upload.py to get one.
        The script will then post the image to Instagram using the Meta Graph API.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('image_url', nargs='?', help='URL of the image to post (optional)')
    parser.add_argument('--caption', default='', help='Caption for the Instagram post')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()

    try:
        if args.verbose:
            print("Starting Instagram post process...")
            print(f"Python executable: {sys.executable}")
            print(f"Working directory: {os.getcwd()}")

        # Load .env with verbose flag
        load_env(verbose=args.verbose)

        # Check required environment variables
        required_vars = [
            'FACEBOOK_APP_ID',
            'FACEBOOK_APP_SECRET',
            'FACEBOOK_ACCESS_TOKEN',
            'INSTAGRAM_BUSINESS_ACCOUNT_ID'
        ]
        
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
            sys.exit(1)

        # Get image URL if not provided
        if not args.image_url:
            if args.verbose:
                print("No image URL provided, attempting to get one from db_upload.py")
            args.image_url = get_image_url(args.verbose)
            if not args.image_url:
                print("Error: Failed to obtain image URL.", file=sys.stderr)
                sys.exit(1)
            if args.verbose:
                print(f"Got image URL: {args.image_url}")

        # Verify Facebook token
        if args.verbose:
            print("Verifying Facebook token...")
        access_token = check_fb_token(args.verbose)
        if not access_token:
            print("Error: Failed to obtain valid Facebook token.", file=sys.stderr)
            sys.exit(1)

        # Post to Instagram
        if args.verbose:
            print(f"Posting to Instagram account: {os.environ['INSTAGRAM_BUSINESS_ACCOUNT_ID']}")
        post_id, error_msg = post_to_instagram(access_token, args.image_url, args.caption, 
                                            os.environ['INSTAGRAM_BUSINESS_ACCOUNT_ID'], args.verbose)
        if not post_id:
            print(f"Error: Failed to create Instagram post. {error_msg}", file=sys.stderr)
            sys.exit(1)

        # Get permalink
        if args.verbose:
            print("Fetching post permalink...")
        permalink = get_instagram_permalink(access_token, post_id, args.verbose)
        if not permalink:
            permalink = f"https://www.instagram.com/p/{post_id}/"
            if args.verbose:
                print(f"Warning: Could not fetch permalink, using fallback URL: {permalink}")

        # Output the result
        if not args.verbose:
            print(permalink)
        else:
            print("\nSuccess! Instagram post created:")
        print(permalink)
        
        sys.exit(0)

    except Exception as e:
        if args.verbose:
            import traceback
            print(f"\nError: {str(e)}", file=sys.stderr)
            print("\nStack trace:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

# Load environment variables at module level
load_env(verbose=True)

if __name__ == "__main__":
    main()