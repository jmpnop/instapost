"""API commands that run on the remote VM."""

import sys
from instapost.config import load_settings
from instapost.clients.instagram import InstagramClient


def token_info():
    """Print Facebook token information."""
    settings = load_settings()
    token = settings.instagram.get_token_info()
    expires = token.get_expiration_date()

    print("Facebook Access Token")
    print("=" * 40)
    print("Valid: True")
    if expires and expires.year > 2000:
        print(f"Expires: {expires.strftime('%Y-%m-%d %H:%M')}")
    else:
        print("Expires: Never (long-lived)")
    scopes = token.get_scopes()
    if scopes:
        print(f"Scopes: {', '.join(scopes)}")
    print(f"App ID: {token.app_id}")


def account():
    """Print Instagram account information."""
    settings = load_settings()
    client = InstagramClient(settings.instagram)
    info = client.get_account_info()

    print("Instagram Account")
    print("=" * 40)
    print(f"Username: @{info.get('username')}")
    print(f"Name: {info.get('name')}")
    print(f"Followers: {info.get('followers_count')}")
    print(f"Posts: {info.get('media_count')}")


def media(limit: int = 5):
    """Print recent Instagram posts."""
    settings = load_settings()
    client = InstagramClient(settings.instagram)
    result = client.get_media(limit)

    print(f"Recent Posts (last {limit})")
    print("=" * 50)
    print()

    for item in result.get('data', []):
        caption = item.get('caption', 'No caption')
        if len(caption) > 60:
            caption = caption[:60] + '...'
        print(f"📷 {item.get('media_type', 'POST')}")
        print(f"   {caption}")
        print(f"   {item.get('permalink')}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m instapost.api_commands <command> [args]")
        print("Commands: token-info, account, media [limit]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "token-info":
        token_info()
    elif cmd == "account":
        account()
    elif cmd == "media":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        media(limit)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
