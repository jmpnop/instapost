"""Configuration handling for the instapost package."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator

from instapost.clients.facebook import FacebookToken, FacebookTokenError


class DropboxConfig(BaseModel):
    """Configuration for Dropbox API."""

    app_key: str = Field(..., description="Dropbox API app key")
    app_secret: str = Field(..., description="Dropbox API app secret")
    refresh_token: str = Field(..., description="Dropbox API refresh token")
    folder_path: str = Field("/INPOST333", description="Dropbox folder path for uploads")


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

    dropbox: DropboxConfig
    instagram: InstagramConfig


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

    # Load Dropbox configuration
    dropbox_config = DropboxConfig(
        app_key=os.environ.get("DROPBOX_APP_KEY", ""),
        app_secret=os.environ.get("DROPBOX_APP_SECRET", ""),
        refresh_token=os.environ.get("DROPBOX_REFRESH_TOKEN", ""),
        folder_path=os.environ.get("DROPBOX_FOLDER_PATH", "/INPOST333"),
    )

    # Load Instagram configuration
    instagram_config = InstagramConfig(
        app_id=os.environ.get("FACEBOOK_APP_ID", ""),
        app_secret=os.environ.get("FACEBOOK_APP_SECRET", ""),
        access_token=os.environ.get("FACEBOOK_ACCESS_TOKEN", ""),
        business_account_id=os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", ""),
    )

    # Create and return settings
    return Settings(dropbox=dropbox_config, instagram=instagram_config)