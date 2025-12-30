"""Dropbox client for uploading images and generating links."""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Tuple

import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.exceptions import AuthError, ApiError
from dropbox.files import FileMetadata

from instapost.config import DropboxConfig


class DropboxClient:
    """Client for interacting with Dropbox API."""

    def __init__(self, config: DropboxConfig):
        """Initialize Dropbox client.

        Args:
            config: Dropbox configuration.
        """
        self.config = config
        self.client = self._get_dropbox_client()

    def _get_dropbox_client(self) -> dropbox.Dropbox:
        """Get authenticated Dropbox client.

        Returns:
            Authenticated Dropbox client.

        Raises:
            AuthError: If authentication fails.
        """
        try:
            return dropbox.Dropbox(
                app_key=self.config.app_key,
                app_secret=self.config.app_secret,
                oauth2_refresh_token=self.config.refresh_token,
            )
        except AuthError as e:
            raise AuthError(f"Failed to authenticate with Dropbox: {e}")

    @staticmethod
    def generate_auth_flow() -> Tuple[str, DropboxOAuth2FlowNoRedirect]:
        """Generate authentication flow for Dropbox API.

        Returns:
            Tuple of authorization URL and OAuth flow object.
        """
        # This is a helper method for users to get their refresh token
        app_key = input("Enter your Dropbox app key: ")
        app_secret = input("Enter your Dropbox app secret: ")

        auth_flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret)
        auth_url = auth_flow.start()

        return auth_url, auth_flow

    @staticmethod
    def complete_auth_flow(auth_flow: DropboxOAuth2FlowNoRedirect, auth_code: str) -> str:
        """Complete authentication flow and get refresh token.

        Args:
            auth_flow: OAuth flow object.
            auth_code: Authorization code from Dropbox.

        Returns:
            Refresh token.
        """
        try:
            oauth_result = auth_flow.finish(auth_code)
            return oauth_result.refresh_token
        except Exception as e:
            raise AuthError(f"Failed to complete authentication flow: {e}")

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
        folder = self.config.folder_path.rstrip('/')
        dropbox_path = f"{folder}/{image_path.name}" if folder else f"/{image_path.name}"

        # Upload file
        try:
            with open(image_path, "rb") as f:
                return self.client.files_upload(
                    f.read(),
                    dropbox_path,
                    mode=dropbox.files.WriteMode.overwrite,
                )
        except ApiError as e:
            raise Exception(f"Failed to upload image to Dropbox: {e}") from e

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

            raise Exception(f"Failed to get shared link: {e}") from e

    def upload_and_get_link(self, image_path: str) -> str:
        """Upload image to Dropbox and get shared link.

        Args:
            image_path: Path to image file.

        Returns:
            Shared link with raw=1 parameter.
        """
        file_metadata = self.upload_image(image_path)
        return self.get_shared_link(file_metadata)


# CLI functionality for standalone usage
if __name__ == "__main__":
    from instapost.config import load_settings

    parser = argparse.ArgumentParser(
        description="Upload image to Dropbox and get shared link"
    )
    parser.add_argument('file', type=str, help='Path to the image file to upload')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    # Load settings
    try:
        settings = load_settings()
        client = DropboxClient(settings.dropbox)

        # Upload and get link
        if args.verbose:
            print(f"Uploading {args.file}...")

        raw_link = client.upload_and_get_link(args.file)

        if args.verbose:
            print(f"Upload successful!")
            print(f"Raw Image URL: {raw_link}")
        else:
            # In non-verbose mode, only print the link (for scheduler to capture)
            print(raw_link)

        sys.exit(0)

    except Exception as e:
        if args.verbose:
            print(f"Error: {e}")
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
