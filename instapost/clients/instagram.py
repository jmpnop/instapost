"""Instagram client for posting images using Facebook Graph API."""

import os
import sys
import json
import time
import argparse
import logging
from typing import Dict, Optional, Any

import requests

from instapost.config import InstagramConfig
from instapost.retry import retry_instagram_operation

logger = logging.getLogger(__name__)

# Import FacebookTokenError from facebook client
try:
    from instapost.clients.facebook import FacebookTokenError
except ImportError:
    # Fallback for development
    class FacebookTokenError(Exception):
        pass


class InstagramClient:
    """Client for posting to Instagram using Facebook Graph API."""

    # Facebook Graph API base URL
    API_BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, config: InstagramConfig):
        """Initialize Instagram client.

        Args:
            config: Instagram configuration.
        """
        self.config = config

    def _validate_token(self) -> None:
        """Validate the Facebook access token before making API requests.

        Raises:
            ValueError: If the token is invalid or expired.
        """
        try:
            # Validate the token
            if not self.config.validate_token():
                raise ValueError("Invalid Facebook access token")

            # Check if the token is expired or will expire soon (within 1 day)
            if self.config.is_token_expired():
                raise ValueError("Facebook access token is expired or will expire soon")
        except FacebookTokenError as e:
            raise ValueError(f"Error validating Facebook access token: {str(e)}")

    def get_token_info(self) -> Dict[str, Any]:
        """Get information about the Facebook access token.

        Returns:
            Dict[str, Any]: Token information.

        Raises:
            ValueError: If there's an error getting token information.
        """
        try:
            token = self.config.get_token_info()

            # Get token information
            info = {
                "is_valid": token.validate(),
                "expires_at": token.get_expiration_date(),
                "scopes": token.get_scopes(),
                "user_id": token.get_user_id(),
                "app_id": token.get_app_id(),
                "token_type": token.get_token_type(),
            }

            return info
        except FacebookTokenError as e:
            raise ValueError(f"Error getting token information: {str(e)}")

    @retry_instagram_operation
    def post_image(
        self, image_url: str, caption: str = "", location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Post image to Instagram with automatic retry on failures.

        Args:
            image_url: URL of the image to post (must be publicly accessible).
            caption: Caption for the post.
            location_id: Optional Instagram location ID.

        Returns:
            Response from the API containing post ID and permalink.

        Raises:
            ValueError: If the API request fails or the token is invalid.
            RetryError: If all retry attempts are exhausted.
        """
        # Validate the token before making API requests
        self._validate_token()

        # Endpoint for creating a media container
        media_url = f"{self.API_BASE_URL}/{self.config.business_account_id}/media"

        # Prepare parameters for creating a media container
        params = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.config.access_token,
        }

        if location_id:
            params["location_id"] = location_id

        # Create a media container
        response = requests.post(media_url, params=params)
        if not response.ok:
            error_message = f"Failed to create media container: {response.text}"
            raise ValueError(error_message)

        creation_id = response.json().get("id")
        if not creation_id:
            raise ValueError("Failed to get creation ID from response")

        # Wait for Instagram to process the media (Instagram needs time to fetch and process the image)
        # Retry up to 5 times with exponential backoff
        max_retries = 5
        retry_delay = 2  # Start with 2 seconds

        for attempt in range(max_retries):
            if attempt > 0:
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff

            # Publish the media container
            publish_url = f"{self.API_BASE_URL}/{self.config.business_account_id}/media_publish"
            publish_params = {
                "creation_id": creation_id,
                "access_token": self.config.access_token,
            }

            publish_response = requests.post(publish_url, params=publish_params)

            # Check for "media not ready" error
            if not publish_response.ok:
                error_data = publish_response.json()
                if error_data.get("error", {}).get("error_subcode") == 2207027:
                    # Media not ready yet, retry
                    if attempt < max_retries - 1:
                        continue  # Try again
                    else:
                        # Last attempt failed
                        error_message = f"Failed to publish media after {max_retries} attempts: {publish_response.text}"
                        raise ValueError(error_message)
                else:
                    # Different error, don't retry
                    error_message = f"Failed to publish media: {publish_response.text}"
                    raise ValueError(error_message)

            # Success!
            break

        post_id = publish_response.json().get("id")

        # Get permalink
        permalink = self.get_permalink(post_id)

        return {
            "id": post_id,
            "permalink": permalink
        }

    def get_permalink(self, post_id: str) -> str:
        """Get permalink for a post.

        Args:
            post_id: Instagram post ID.

        Returns:
            Permalink URL.
        """
        permalink_url = f"{self.API_BASE_URL}/{post_id}"
        params = {
            "fields": "permalink",
            "access_token": self.config.access_token,
        }

        response = requests.get(permalink_url, params=params)
        if response.ok:
            permalink = response.json().get("permalink")
            if permalink:
                return permalink

        # Fallback to constructed URL
        return f"https://www.instagram.com/p/{post_id}/"

    def get_account_info(self) -> Dict[str, Any]:
        """Get information about the Instagram business account.

        Returns:
            Account information.

        Raises:
            ValueError: If the API request fails or the token is invalid.
        """
        # Validate the token before making API requests
        self._validate_token()

        url = f"{self.API_BASE_URL}/{self.config.business_account_id}"
        params = {
            "fields": "name,username,profile_picture_url,followers_count,media_count",
            "access_token": self.config.access_token,
        }

        response = requests.get(url, params=params)
        if not response.ok:
            error_message = f"Failed to get account info: {response.text}"
            raise ValueError(error_message)

        return response.json()

    def get_media(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent media from the Instagram business account.

        Args:
            limit: Maximum number of media items to return.

        Returns:
            Recent media items.

        Raises:
            ValueError: If the API request fails or the token is invalid.
        """
        # Validate the token before making API requests
        self._validate_token()

        url = f"{self.API_BASE_URL}/{self.config.business_account_id}/media"
        params = {
            "fields": "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp",
            "limit": limit,
            "access_token": self.config.access_token,
        }

        response = requests.get(url, params=params)
        if not response.ok:
            error_message = f"Failed to get media: {response.text}"
            raise ValueError(error_message)

        return response.json()


# CLI functionality for standalone usage
if __name__ == "__main__":
    from instapost.config import load_settings

    parser = argparse.ArgumentParser(
        description="Post image to Instagram using Facebook Graph API"
    )
    parser.add_argument('image_url', type=str, help='URL of the image to post (must be publicly accessible)')
    parser.add_argument('--caption', default='', help='Caption for the Instagram post (default: empty)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    try:
        # Load settings
        settings = load_settings()
        client = InstagramClient(settings.instagram)

        # Post image
        if args.verbose:
            print(f"Posting image to Instagram...")
            print(f"Image URL: {args.image_url}")
            print(f"Caption: {args.caption or '(empty)'}")

        result = client.post_image(args.image_url, args.caption)

        if args.verbose:
            print(f"Post successful!")
            print(f"Post ID: {result['id']}")
            print(f"Permalink: {result['permalink']}")
        else:
            # In non-verbose mode, only print the permalink (for scheduler to capture)
            print(result['permalink'])

        sys.exit(0)

    except Exception as e:
        if args.verbose:
            import traceback
            print(f"Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
