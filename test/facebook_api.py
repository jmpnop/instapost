#!/usr/bin/env python3
"""Test script for Facebook token validation."""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from instapost.config import load_settings
from instapost.clients.facebook import FacebookToken, FacebookTokenError


def test_facebook_token():
    """Test Facebook token validation with detailed reporting."""
    print("\n=== Testing Facebook Token ===")

    try:
        # Load settings
        print("Loading configuration...")
        settings = load_settings()

        print(f"App ID: {settings.instagram.app_id}")
        print(f"Access Token: {settings.instagram.access_token[:20]}...")

        # Initialize token validator
        print("\nValidating Facebook token...")
        token = FacebookToken(
            token=settings.instagram.access_token,
            app_id=settings.instagram.app_id,
            app_secret=settings.instagram.app_secret
        )

        # Validate token
        is_valid = token.validate()
        if is_valid:
            print("✅ Token is valid")
        else:
            print("❌ Token is invalid")
            return False

        # Get token details
        print("\n=== Token Details ===")

        # Expiration
        expiration = token.get_expiration_date()
        if expiration:
            print(f"Expires at: {expiration}")

            # Check if expiring soon
            is_expired = token.is_expired(buffer_seconds=86400)  # 1 day buffer
            if is_expired:
                print("⚠️  Warning: Token is expired or will expire within 24 hours")
            else:
                print("✅ Token is valid and not expiring soon")
        else:
            print("Expiration: Never (long-lived token)")

        # Scopes
        scopes = token.get_scopes()
        print(f"\nPermissions/Scopes:")
        if scopes:
            for scope in scopes:
                print(f"  • {scope}")
        else:
            print("  (No specific scopes returned)")

        # User ID
        user_id = token.get_user_id()
        if user_id:
            print(f"\nUser ID: {user_id}")

        # App ID
        app_id = token.get_app_id()
        print(f"App ID: {app_id}")

        # Token type
        token_type = token.get_token_type()
        print(f"Token Type: {token_type}")

        print("\n=== All Facebook token tests passed! ===")
        return True

    except FacebookTokenError as e:
        print(f"❌ Facebook token error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during Facebook token test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_instagram_config():
    """Test Instagram configuration using InstagramConfig."""
    print("\n=== Testing Instagram Configuration ===")

    try:
        settings = load_settings()

        print(f"App ID: {settings.instagram.app_id}")
        print(f"Business Account ID: {settings.instagram.business_account_id}")
        print(f"Token (first 20 chars): {settings.instagram.access_token[:20]}...")

        # Test token validation through config
        print("\nValidating token through InstagramConfig...")
        is_valid = settings.instagram.validate_token()

        if is_valid:
            print("✅ Token validated successfully")
        else:
            print("❌ Token validation failed")
            return False

        # Check expiration
        is_expired = settings.instagram.is_token_expired(buffer_seconds=86400)
        if is_expired:
            print("⚠️  Warning: Token is expired or expiring within 24 hours")
        else:
            print("✅ Token is valid and not expiring soon")

        # Get full token info
        token_info = settings.instagram.get_token_info()
        print(f"\nToken expiration: {token_info.get_expiration_date()}")

        print("\n=== Instagram configuration tests passed! ===")
        return True

    except Exception as e:
        print(f"❌ Error testing Instagram config: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Facebook token validation")
    parser.add_argument('--config-only', action='store_true',
                       help='Only test Instagram config (not direct token validation)')

    args = parser.parse_args()

    if args.config_only:
        success = test_instagram_config()
    else:
        # Run both tests
        success1 = test_facebook_token()
        success2 = test_instagram_config()
        success = success1 and success2

    sys.exit(0 if success else 1)
