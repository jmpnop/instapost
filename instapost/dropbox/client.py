"""Dropbox client for uploading images and generating links."""

import os
from pathlib import Path
from typing import Optional, Tuple
import base64
import requests
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.exceptions import ApiError
from dropbox.files import FileMetadata

from instapost.config import DropboxConfig


class AuthError(Exception):
    """Exception raised for authentication errors."""
    def __init__(self, message: str, error: Exception = None):
        self.message = message
        self.error = error
        super().__init__(self.message)


class DropboxClient:
    """Client for interacting with Dropbox API."""

    def __init__(self, app_key: str = None, app_secret: str = None, refresh_token: str = None, access_token: str = None):
        """Initialize Dropbox client.

        Args:
            app_key: Dropbox app key or DropboxConfig object.
            app_secret: Dropbox app secret (ignored if app_key is a DropboxConfig).
            refresh_token: Dropbox refresh token (optional).
            access_token: Dropbox access token (optional).
        """
        # Handle case where app_key is a DropboxConfig object
        if hasattr(app_key, 'app_key') and hasattr(app_key, 'app_secret'):
            config = app_key
            self.app_key = config.app_key
            self.app_secret = config.app_secret
            if hasattr(config, 'refresh_token'):
                refresh_token = config.refresh_token or refresh_token
            if hasattr(config, 'access_token'):
                access_token = config.access_token or access_token
        else:
            self.app_key = (app_key or os.getenv("DROPBOX_APP_KEY"))
            self.app_secret = (app_secret or os.getenv("DROPBOX_APP_SECRET"))
        
        # Convert to string and clean up
        self.app_key = str(self.app_key).strip("'\"") if self.app_key else None
        self.app_secret = str(self.app_secret).strip("'\"") if self.app_secret else None
        
        if not (self.app_key and self.app_secret):
            raise AuthError("Dropbox app key and secret must be provided or set in environment variables.")
        
        # Try to use refresh token if available
        if refresh_token or os.getenv("DROPBOX_REFRESH_TOKEN"):
            self.refresh_token = str(refresh_token or os.getenv("DROPBOX_REFRESH_TOKEN")).strip("'\"")
            print("\nInitializing Dropbox client with refresh token...")
            try:
                self.access_token = self._get_refreshed_access_token()
                print("✅ Successfully obtained access token using refresh token")
            except AuthError as e:
                print(f"❌ Failed to get access token with refresh token: {str(e)}")
                raise AuthError("Failed to get access token with refresh token. Please re-authenticate with Dropbox.", error=e)
        # Fall back to access token if provided (not recommended)
        elif access_token or os.getenv("DROPBOX_ACCESS_TOKEN"):
            self.access_token = str(access_token or os.getenv("DROPBOX_ACCESS_TOKEN")).strip("'\"")
            print("\n⚠️  Using short-lived access token. This will expire and need to be refreshed manually.")
        else:
            raise AuthError("Either a refresh token or access token must be provided or set in environment variables.")
        
        try:
            # Initialize the Dropbox client
            self.client = dropbox.Dropbox(
                oauth2_access_token=self.access_token,
                max_retries_on_error=3,
                timeout=30,
            )
            
            # Set the folder path for uploads
            self.folder_path = os.getenv("DROPBOX_FOLDER_PATH", "/InstaPost")
            
            # Create the folder if it doesn't exist
            try:
                self.client.files_create_folder_v2(self.folder_path)
                print(f"✅ Successfully created/verified Dropbox folder: {self.folder_path}")
            except Exception as e:
                if not (isinstance(e, dropbox.exceptions.ApiError) and 
                       e.error.is_path() and 
                       e.error.get_path().is_conflict()):
                    print(f"❌ Error creating Dropbox folder: {str(e)}")
                    raise
                print(f"ℹ️  Dropbox folder already exists: {self.folder_path}")
                    
        except Exception as e:
            error_msg = f"Failed to initialize Dropbox client: {str(e)}"
            print(f"❌ {error_msg}")
            raise AuthError(error_msg, error=e) from e

    def _get_refreshed_access_token(self) -> str:
        """Get a new access token using the refresh token.

        Returns:
            A new access token.

        Raises:
            AuthError: If token refresh fails.
        """
        try:
            # Use the refresh token to get a new access token
            auth_string = f"{self.app_key}:{self.app_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
            }
            
            print(f"\nDebug - Making token refresh request to Dropbox API...")
            print(f"Debug - App Key: {self.app_key}")
            print(f"Debug - App Secret: {self.app_secret[:3]}...{self.app_secret[-3:] if len(self.app_secret) > 6 else ''}")
            print(f"Debug - Refresh Token: {self.refresh_token[:5]}...{self.refresh_token[-5:] if self.refresh_token else ''}")
            
            response = requests.post(
                'https://api.dropbox.com/oauth2/token',
                headers=headers,
                data=data,
                timeout=30
            )
            
            # Print response details for debugging
            print(f"\nDebug - Status Code: {response.status_code}")
            print(f"Debug - Response Headers: {response.headers}")
            print(f"Debug - Response Content: {response.text}")
            
            response.raise_for_status()
            
            try:
                token_data = response.json()
                print(f"Debug - Token Data: {token_data}")
            except ValueError as e:
                raise AuthError(f"Invalid JSON in response: {response.text}", error=e)
            
            if 'access_token' not in token_data:
                raise AuthError(f"No access token in refresh response. Response: {token_data}")
                
            return token_data['access_token']
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = f"{e.response.status_code} {e.response.reason}: {error_data}"
                    print(f"Debug - Error Response: {error_msg}")
                except ValueError:
                    error_msg = f"{e.response.status_code} {e.response.reason}: {e.response.text or 'No error details'}"
                    print(f"Debug - Error Response (non-JSON): {error_msg}")
            
            # Check for common issues
            if "invalid_client" in error_msg:
                error_msg += "\nThe app key or secret is invalid. Please check your Dropbox app credentials."
            elif "invalid_grant" in error_msg:
                error_msg += "\nThe refresh token is invalid or expired. Please re-authenticate with Dropbox."
            elif "unsupported_grant_type" in error_msg:
                error_msg += "\nThe grant type is not supported. This might be an issue with the Dropbox API configuration."
            
            raise AuthError(f"Failed to refresh access token: {error_msg}", error=e) from e
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"Debug - Unexpected error: {error_msg}")
            print(f"Debug - Error type: {type(e).__name__}")
            print(f"Debug - Error details: {str(e)}")
            raise AuthError(f"Failed to refresh access token: {error_msg}", error=e) from e

    @staticmethod
    def generate_auth_flow() -> Tuple[str, DropboxOAuth2FlowNoRedirect]:
        """Generate authentication flow for Dropbox API with offline access.

        Returns:
            Tuple of authorization URL and OAuth flow object.
        """
        print("\n" + "="*50)
        print("Dropbox App Authentication")
        print("="*50)
        print("Please enter your Dropbox app credentials.")
        print("You can find these at https://www.dropbox.com/developers/apps")
        print("="*50)
        
        app_key = input("Enter your Dropbox app key: ").strip()
        app_secret = input("Enter your Dropbox app secret: ").strip()

        # Create OAuth2 flow with offline access
        auth_flow = DropboxOAuth2FlowNoRedirect(
            app_key,
            app_secret,
            token_access_type='offline',
            use_pkce=True
        )
        
        # Generate the authorization URL with the required scopes
        auth_url = auth_flow.start()
        
        print("\n" + "="*50)
        print("IMPORTANT: Make sure your app has these permissions in the Dropbox App Console:")
        print("- files.content.write")
        print("- sharing.write")
        print("- account_info.read")
        print("\nThen, click this link to authorize the app:")
        print(auth_url)
        print("\nAfter authorizing, copy the authorization code and paste it below.")
        print("="*50 + "\n")
        
        return auth_url, auth_flow

    @staticmethod
    def complete_auth_flow(auth_flow: DropboxOAuth2FlowNoRedirect, auth_code: str) -> str:
        """Complete authentication flow and get refresh token.

        Args:
            auth_flow: OAuth flow object.
            auth_code: Authorization code from Dropbox.

        Returns:
            Refresh token as a string.
            
        Raises:
            AuthError: If authentication fails or no refresh token is returned.
        """
        try:
            print("\nExchanging authorization code for tokens...")
            
            # Clean the auth code
            auth_code = auth_code.strip()
            
            # Complete the OAuth flow
            oauth_result = auth_flow.finish(auth_code)
            
            # Debug output
            print("\nOAuth result received. Available attributes:")
            for attr in dir(oauth_result):
                if not attr.startswith('_'):
                    print(f"- {attr}: {getattr(oauth_result, attr, 'N/A')}")
            
            # The refresh token should be available directly in the oauth_result
            if hasattr(oauth_result, 'refresh_token') and oauth_result.refresh_token:
                print("\n✅ Successfully obtained refresh token!")
                return oauth_result.refresh_token
            
            # If not found directly, check the _oauth2_flow.credentials
            if hasattr(auth_flow, '_oauth2_flow') and hasattr(auth_flow._oauth2_flow, 'credentials'):
                creds = auth_flow._oauth2_flow.credentials
                if hasattr(creds, 'refresh_token') and creds.refresh_token:
                    print("\n✅ Successfully obtained refresh token from credentials!")
                    return creds.refresh_token
            
            # If we still don't have a refresh token, check for it in the raw result
            if hasattr(oauth_result, '_oauth2_flow') and hasattr(oauth_result._oauth2_flow, 'credentials'):
                creds = oauth_result._oauth2_flow.credentials
                if hasattr(creds, 'refresh_token') and creds.refresh_token:
                    print("\n✅ Successfully obtained refresh token from OAuth2 flow!")
                    return creds.refresh_token
            
            # If we get here, we couldn't find a refresh token
            raise AuthError(
                "No refresh token in OAuth result. "
                "Make sure your app has 'offline' access enabled and 'token_access_type' is set to 'offline'."
            )
                
        except Exception as e:
            error_message = f"Error in complete_auth_flow: {str(e)}"
            print(f"\n❌ {error_message}")
            print(f"Error type: {type(e).__name__}")
            
            # For OAuth2 specific errors
            if hasattr(e, 'error') and e.error:
                error_message = str(e.error)
                print(f"OAuth error: {error_message}")
                if hasattr(e, 'error_description'):
                    print(f"Error description: {e.error_description}")
            
            # For HTTP errors
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                content = e.response.content
                print(f"Response content: {content}")
                if b'invalid_grant' in content:
                    error_message = "The authorization code is invalid or has expired. Please try again with a new code."
            
            raise AuthError(error_message, error=e) from e

    def upload_image(self, image_path: str) -> FileMetadata:
        """Upload image to Dropbox.

        Args:
            image_path: Path to image file.

        Returns:
            Metadata of uploaded file.

        Raises:
            FileNotFoundError: If image file does not exist.
            ApiError: If upload fails.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Determine destination path in Dropbox
        dropbox_path = f"{self.folder_path}/{image_path.name}"

        # Upload file
        try:
            with open(image_path, "rb") as f:
                return self.client.files_upload(
                    f.read(),
                    dropbox_path,
                    mode=dropbox.files.WriteMode.overwrite,
                )
        except ApiError as e:
            raise ApiError(f"Failed to upload image to Dropbox: {e}")

    def get_shared_link(self, file_metadata: FileMetadata) -> str:
        """Get shared link for uploaded file.

        Args:
            file_metadata: Metadata of uploaded file.

        Returns:
            Shared link with raw=1 parameter.

        Raises:
            ApiError: If getting shared link fails.
        """
        try:
            # Create shared link
            shared_link_metadata = self.client.sharing_create_shared_link_with_settings(
                file_metadata.path_display
            )
            
            # Convert to raw link (dl=0 to raw=1)
            url = shared_link_metadata.url
            raw_url = url.replace("www.dropbox.com", "dl.dropboxusercontent.com")
            raw_url = raw_url.replace("?dl=0", "?raw=1")
            
            return raw_url
        except ApiError as e:
            # Check if link already exists
            if e.error.is_shared_link_already_exists():
                shared_links = self.client.sharing_list_shared_links(
                    file_metadata.path_display
                ).links
                if shared_links:
                    url = shared_links[0].url
                    raw_url = url.replace("www.dropbox.com", "dl.dropboxusercontent.com")
                    raw_url = raw_url.replace("?dl=0", "?raw=1")
                    return raw_url
            
            raise ApiError(f"Failed to get shared link: {e}")

    def upload_and_get_link(self, image_path: str) -> str:
        """Upload image to Dropbox and get shared link.

        Args:
            image_path: Path to image file.

        Returns:
            Shared link with raw=1 parameter.
        """
        file_metadata = self.upload_image(image_path)
        return self.get_shared_link(file_metadata)