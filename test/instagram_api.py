#!/usr/bin/env python3
"""Test script for Instagram API integration."""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load environment using dotenv since post.py was merged into clients/instagram.py
from dotenv import load_dotenv

def load_env(file_path=None, verbose=False):
    """Load environment variables from .env file."""
    if file_path is None:
        file_path = PROJECT_ROOT / '.env'

    if verbose:
        print(f"Loading environment from: {file_path}")

    load_dotenv(file_path)
    return True

def test_instagram_post(image_url):
    """Test Instagram post with detailed error reporting."""
    load_env(verbose=True)
    
    access_token = os.environ.get('FACEBOOK_ACCESS_TOKEN')
    ig_account_id = os.environ.get('INSTAGRAM_BUSINESS_ACCOUNT_ID')
    
    print("\n=== Testing Instagram API ===")
    print(f"Account ID: {ig_account_id}")
    print(f"Access Token: {access_token[:10]}..." if access_token else "No access token found")
    print(f"Image URL: {image_url}")
    
    # Step 1: Create media container
    try:
        create_url = f"https://graph.facebook.com/v20.0/{ig_account_id}/media"
        create_params = {
            'image_url': image_url,
            'caption': 'Test post from InstaPost',
            'access_token': access_token
        }
        create_data = urllib.parse.urlencode(create_params).encode('utf-8')
        
        print("\nCreating media container...")
        create_req = urllib.request.Request(create_url, data=create_data, method='POST')
        with urllib.request.urlopen(create_req) as response:
            create_info = json.loads(response.read().decode('utf-8'))
            print("Create Response:", json.dumps(create_info, indent=2))
            
            if 'id' not in create_info:
                print("\n❌ Failed to create media container. Check your access token and permissions.")
                return
                
            container_id = create_info['id']
            print(f"✅ Container created: {container_id}")
            
    except Exception as e:
        print(f"\n❌ Error creating container: {str(e)}")
        if hasattr(e, 'read'):
            try:
                error_data = json.loads(e.read().decode('utf-8'))
                print("Error details:", json.dumps(error_data, indent=2))
            except:
                print("Could not read error details")
        return

if __name__ == "__main__":
    test_image_url = "https://www.dropbox.com/scl/fi/yzmsre12rh1rqoyctitie/Screenshot-2025-08-12-at-12.38.52-PM.png?rlkey=vqqnvoykvo1e5g658ur64pfk9&raw=1"
    test_instagram_post(test_image_url)
