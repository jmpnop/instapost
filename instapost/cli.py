"""Command-line interface for instapost."""

import os
import sys
from pathlib import Path
from typing import Optional

import click

from instapost.config import load_settings
from instapost.dropbox.client import DropboxClient
from instapost.instagram.client import InstagramClient


@click.group()
@click.option(
    "--env-file",
    "-e",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    help="Path to .env file with API credentials.",
)
@click.pass_context
def cli(ctx: click.Context, env_file: Optional[str] = None):
    """Post images to Instagram using Facebook Graph API and Dropbox."""
    try:
        # Load settings from .env file
        settings = load_settings(env_file)
        
        # Initialize clients
        dropbox_client = DropboxClient(settings.dropbox)
        instagram_client = InstagramClient(settings.instagram)
        
        # Store clients in context
        ctx.obj = {
            "settings": settings,
            "dropbox_client": dropbox_client,
            "instagram_client": instagram_client,
        }
    except Exception as e:
        click.echo(f"Error initializing clients: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("image_path", type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True))
@click.option("--caption", "-c", required=True, help="Caption for the Instagram post.")
@click.option("--location-id", "-l", help="Instagram location ID (optional).")
@click.pass_context
def post(ctx: click.Context, image_path: str, caption: str, location_id: Optional[str] = None):
    """Upload image to Dropbox and post it to Instagram.
    
    IMAGE_PATH is the path to the image file to upload.
    """
    dropbox_client = ctx.obj["dropbox_client"]
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Upload image to Dropbox and get shared link
        click.echo("Uploading image to Dropbox...")
        image_url = dropbox_client.upload_and_get_link(image_path)
        click.echo(f"Image uploaded: {image_url}")
        
        # Post image to Instagram
        click.echo("Posting image to Instagram...")
        response = instagram_client.post_image(image_url, caption, location_id)
        click.echo(f"Image posted to Instagram. Post ID: {response.get('id')}")
    except Exception as e:
        click.echo(f"Error posting image: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def account_info(ctx: click.Context):
    """Get information about the Instagram business account."""
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Get account information
        info = instagram_client.get_account_info()
        
        # Display account information
        click.echo("Instagram Account Information:")
        click.echo(f"Name: {info.get('name')}")
        click.echo(f"Username: {info.get('username')}")
        click.echo(f"Followers: {info.get('followers_count')}")
        click.echo(f"Media Count: {info.get('media_count')}")
    except Exception as e:
        click.echo(f"Error getting account information: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--limit", "-n", type=int, default=5, help="Number of recent media items to display.")
@click.pass_context
def recent_media(ctx: click.Context, limit: int):
    """Get recent media from the Instagram business account."""
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Get recent media
        media = instagram_client.get_media(limit)
        
        # Display recent media
        click.echo(f"Recent Instagram Media (up to {limit} items):")
        for item in media.get("data", []):
            click.echo(f"ID: {item.get('id')}")
            click.echo(f"Type: {item.get('media_type')}")
            click.echo(f"Caption: {item.get('caption', 'No caption')[:50]}...")
            click.echo(f"URL: {item.get('permalink')}")
            click.echo("---")
    except Exception as e:
        click.echo(f"Error getting recent media: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def token_info(ctx: click.Context):
    """Check Facebook token validity, expiration, and properties."""
    instagram_client = ctx.obj["instagram_client"]
    
    try:
        # Get token information
        token_info = instagram_client.get_token_info()
        
        # Display token information
        click.echo("Facebook Access Token Information:")
        click.echo(f"Valid: {token_info.get('is_valid', False)}")
        
        # Display expiration date if available
        expires_at = token_info.get('expires_at')
        if expires_at:
            click.echo(f"Expires At: {expires_at}")
        else:
            click.echo("Expires At: Never (long-lived token)")
        
        # Display scopes
        scopes = token_info.get('scopes', [])
        if scopes:
            click.echo("Scopes:")
            for scope in scopes:
                click.echo(f"  - {scope}")
        else:
            click.echo("Scopes: None or not available")
        
        # Display user ID and app ID
        click.echo(f"User ID: {token_info.get('user_id', 'Not available')}")
        click.echo(f"App ID: {token_info.get('app_id', 'Not available')}")
        click.echo(f"Token Type: {token_info.get('token_type', 'Not available')}")
    except Exception as e:
        click.echo(f"Error checking token information: {e}", err=True)
        sys.exit(1)


@cli.command()
def setup_dropbox():
    """Set up Dropbox authentication and get refresh token."""
    try:
        # Generate authentication flow
        auth_url, auth_flow = DropboxClient.generate_auth_flow()
        
        # Display instructions
        click.echo("1. Go to the following URL in your browser:")
        click.echo(auth_url)
        click.echo("2. Click 'Allow' (you might need to log in first).")
        click.echo("3. Copy the authorization code.")
        
        # Get authorization code
        auth_code = click.prompt("Enter the authorization code")
        
        # Complete authentication flow
        refresh_token = DropboxClient.complete_auth_flow(auth_flow, auth_code)
        
        # Display refresh token
        click.echo("\nDropbox authentication successful!")
        click.echo(f"Refresh Token: {refresh_token}")
        click.echo("\nAdd this token to your .env file as DROPBOX_REFRESH_TOKEN.")
    except Exception as e:
        click.echo(f"Error setting up Dropbox authentication: {e}", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()