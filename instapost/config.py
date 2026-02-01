"""Configuration handling for the instapost package."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from instapost.clients.facebook import FacebookToken, FacebookTokenError


class VMConfig(BaseModel):
    """Configuration for remote VM connection."""

    host: str = Field("instapost-deploy", description="SSH host alias or user@hostname")
    instapost_dir: str = Field("/home/ironsirens/instapost", description="Remote instapost directory")
    images_dir: str = Field("/mnt/s3/images", description="Remote images directory")
    processed_dir: str = Field("/mnt/s3/processed", description="Remote processed directory")


class StaticHostingConfig(BaseModel):
    """Configuration for self-hosted images via Angie + Cloudflare tunnel."""

    base_url: str = Field(..., description="Base URL for self-hosted images")


class InstagramConfig(BaseModel):
    """Configuration for Instagram API via Facebook Graph API."""

    app_id: str = Field(..., description="Facebook app ID")
    app_secret: str = Field(..., description="Facebook app secret")
    access_token: str = Field(..., description="Facebook access token")
    business_account_id: str = Field(..., description="Instagram business account ID")
    _token: Optional[FacebookToken] = None

    def validate_token(self) -> bool:
        """Validate the Facebook access token.

        Returns:
            bool: True if the token is valid, False otherwise.

        Raises:
            FacebookTokenError: If there's an error validating the token.
        """
        if not self._token:
            self._token = FacebookToken(
                token=self.access_token,
                app_id=self.app_id,
                app_secret=self.app_secret
            )

        return self._token.validate()

    def is_token_expired(self, buffer_seconds: int = 86400) -> bool:
        """Check if the Facebook access token is expired or will expire soon.

        Args:
            buffer_seconds: Number of seconds to use as a buffer (default: 1 day).
                           If the token expires within this buffer, it's considered expired.

        Returns:
            bool: True if the token is expired or will expire within the buffer time,
                  False otherwise.

        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if not self._token:
            self._token = FacebookToken(
                token=self.access_token,
                app_id=self.app_id,
                app_secret=self.app_secret
            )
            self._token.validate()

        return self._token.is_expired(buffer_seconds)

    def get_token_info(self) -> FacebookToken:
        """Get the Facebook token utility object.

        Returns:
            FacebookToken: The Facebook token utility object.

        Raises:
            FacebookTokenError: If there's an error validating the token.
        """
        if not self._token:
            self._token = FacebookToken(
                token=self.access_token,
                app_id=self.app_id,
                app_secret=self.app_secret
            )
            self._token.validate()

        return self._token


class Settings(BaseModel):
    """Application settings."""

    vm: VMConfig
    instagram: InstagramConfig
    static_hosting: StaticHostingConfig


def load_settings(env_file: Optional[str] = None) -> Settings:
    """Load settings from environment variables or .env file.

    Args:
        env_file: Path to .env file. If None, will try to load from .env in:
                 1. Current working directory
                 2. instapost package directory
                 3. Project root directory

    Returns:
        Settings object with all configuration values.

    Raises:
        ValueError: If required environment variables are missing.
    """
    def find_env_file() -> Optional[str]:
        """Find the most appropriate .env file to load."""
        # 1. Check if explicitly provided
        if env_file and os.path.exists(env_file):
            return os.path.abspath(env_file)

        # 2. Check current working directory
        cwd_env = os.path.abspath('.env')
        if os.path.exists(cwd_env):
            return cwd_env

        # 3. Check instapost package directory
        package_dir = os.path.dirname(os.path.abspath(__file__))
        package_env = os.path.join(package_dir, '.env')
        if os.path.exists(package_env):
            return package_env

        # 4. Check project root (one level up from package)
        root_env = os.path.join(os.path.dirname(package_dir), '.env')
        if os.path.exists(root_env):
            return root_env

        return None

    # Find and load the most appropriate .env file
    found_env = find_env_file()
    if found_env:
        load_dotenv(found_env, override=True)

    # Load VM configuration
    vm_config = VMConfig(
        host=os.environ.get("VM_HOST", "instapost-deploy"),
        instapost_dir=os.environ.get("VM_INSTAPOST_DIR", "/home/ironsirens/instapost"),
        images_dir=os.environ.get("VM_IMAGES_DIR", "/mnt/s3/images"),
        processed_dir=os.environ.get("VM_PROCESSED_DIR", "/mnt/s3/processed"),
    )

    # Load static hosting configuration
    static_hosting_config = StaticHostingConfig(
        base_url=os.environ.get("IMAGE_BASE_URL", "https://instapost.celestialtech.io"),
    )

    # Load Instagram configuration
    instagram_config = InstagramConfig(
        app_id=os.environ.get("FACEBOOK_APP_ID", ""),
        app_secret=os.environ.get("FACEBOOK_APP_SECRET", ""),
        access_token=os.environ.get("FACEBOOK_ACCESS_TOKEN", ""),
        business_account_id=os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", ""),
    )

    # Create and return settings
    return Settings(
        vm=vm_config,
        instagram=instagram_config,
        static_hosting=static_hosting_config,
    )
