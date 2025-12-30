"""Facebook token utilities for the instapost package."""

import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests


class FacebookTokenError(Exception):
    """Exception raised for Facebook token errors."""

    pass


@dataclass
class FacebookToken:
    """Facebook access token with validation and expiration checking.
    
    This class provides utilities for:
    - Validating a Facebook access token
    - Checking if a token is expired or about to expire
    - Accessing token properties (app_id, user_id, scopes, etc.)
    """

    token: str
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    _token_info: Optional[Dict[str, Any]] = None
    _debug_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize token properties by decoding the token."""
        # Parse token data from the token string
        self._parse_token()

    def _parse_token(self) -> None:
        """Parse the token to extract basic information.
        
        Facebook tokens are not JWTs, but we can extract some basic info
        from the token structure.
        """
        try:
            # Facebook tokens have 2 or 3 parts separated by periods
            parts = self.token.split('.')
            if len(parts) >= 2:
                # Try to decode the payload (second part)
                # Add padding if needed
                padding = '=' * (4 - len(parts[1]) % 4)
                decoded = base64.b64decode(parts[1] + padding)
                payload = json.loads(decoded)
                self._token_info = payload
        except Exception:
            # If we can't parse the token, that's fine
            # We'll validate it properly with the Facebook API
            self._token_info = None

    def validate(self) -> bool:
        """Validate the token with Facebook Graph API.
        
        Returns:
            bool: True if the token is valid, False otherwise.
            
        Raises:
            FacebookTokenError: If there's an error validating the token.
        """
        if not self.app_id or not self.app_secret:
            raise FacebookTokenError(
                "App ID and App Secret are required to validate the token"
            )

        try:
            # Use the debug_token endpoint to validate the token
            response = requests.get(
                "https://graph.facebook.com/debug_token",
                params={
                    "input_token": self.token,
                    "access_token": f"{self.app_id}|{self.app_secret}",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            if "data" not in data:
                return False
                
            self._debug_info = data["data"]
            
            # Check if the token is valid
            return self._debug_info.get("is_valid", False)
        except requests.RequestException as e:
            raise FacebookTokenError(f"Error validating token: {str(e)}") from e

    def is_expired(self, buffer_seconds: int = 0) -> bool:
        """Check if the token is expired or will expire soon.

        Args:
            buffer_seconds: Number of seconds to use as a buffer.
                           If the token expires within this buffer, it's considered expired.

        Returns:
            bool: True if the token is expired or will expire within the buffer time,
                  False otherwise.

        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before checking expiration"
            )

        # Check if the token has an expiration time
        if "expires_at" not in self._debug_info:
            # Some tokens don't expire
            return False

        # Get the expiration timestamp
        expires_at = self._debug_info["expires_at"]

        # Page Access Tokens have expires_at=0 or a very old date (epoch) meaning "never expires"
        # Timestamp 0 = 1970-01-01, anything before 2000 is likely a sentinel value
        if expires_at < 946684800:  # January 1, 2000 timestamp
            # This is a never-expiring token (Page Access Token)
            return False

        # Check if the token is expired or will expire soon
        return time.time() + buffer_seconds >= expires_at

    def expires_in(self) -> Optional[timedelta]:
        """Get the time until the token expires.
        
        Returns:
            Optional[timedelta]: Time until expiration, or None if the token doesn't expire.
            
        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before checking expiration"
            )
            
        # Check if the token has an expiration time
        if "expires_at" not in self._debug_info:
            # Some tokens don't expire
            return None
            
        # Get the expiration timestamp
        expires_at = self._debug_info["expires_at"]
        
        # Calculate the time until expiration
        seconds_until_expiration = expires_at - time.time()
        if seconds_until_expiration <= 0:
            return timedelta(seconds=0)
            
        return timedelta(seconds=seconds_until_expiration)

    def get_expiration_date(self) -> Optional[datetime]:
        """Get the token expiration date.
        
        Returns:
            Optional[datetime]: Expiration date, or None if the token doesn't expire.
            
        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before checking expiration"
            )
            
        # Check if the token has an expiration time
        if "expires_at" not in self._debug_info:
            # Some tokens don't expire
            return None
            
        # Get the expiration timestamp
        expires_at = self._debug_info["expires_at"]
        
        # Convert to datetime - display all timestamps as is, even if they're 0 or 1
        return datetime.fromtimestamp(expires_at)

    def get_scopes(self) -> list[str]:
        """Get the scopes associated with the token.
        
        Returns:
            list[str]: List of scopes.
            
        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before getting scopes"
            )
            
        # Get the scopes
        scopes = self._debug_info.get("scopes", [])
        return scopes

    def get_user_id(self) -> Optional[str]:
        """Get the user ID associated with the token.
        
        Returns:
            Optional[str]: User ID, or None if not available.
            
        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before getting user ID"
            )
            
        # Get the user ID
        return self._debug_info.get("user_id")

    def get_app_id(self) -> Optional[str]:
        """Get the app ID associated with the token.
        
        Returns:
            Optional[str]: App ID, or None if not available.
            
        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before getting app ID"
            )
            
        # Get the app ID
        return self._debug_info.get("app_id")

    def get_token_type(self) -> Optional[str]:
        """Get the token type.
        
        Returns:
            Optional[str]: Token type, or None if not available.
            
        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before getting token type"
            )
            
        # Get the token type
        return self._debug_info.get("type")

    def get_debug_info(self) -> Dict[str, Any]:
        """Get the full debug info for the token.
        
        Returns:
            Dict[str, Any]: Debug info.
            
        Raises:
            FacebookTokenError: If the token hasn't been validated yet.
        """
        if self._debug_info is None:
            raise FacebookTokenError(
                "Token must be validated before getting debug info"
            )
            
        return self._debug_info