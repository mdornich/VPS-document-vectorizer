#!/usr/bin/env python3
"""
OAuth setup with manual URL for incognito mode
"""

import os
import pickle
import webbrowser
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def setup_oauth():
    """Run OAuth flow with manual URL option"""
    creds = None
    token_path = 'config/token.json'
    client_secrets_path = 'config/client_secrets.json'
    
    Path('config').mkdir(exist_ok=True)
    
    if not os.path.exists(client_secrets_path):
        print(f"❌ Error: {client_secrets_path} not found!")
        return False
    
    print("=" * 60)
    print("Google Drive OAuth Setup")
    print("=" * 60)
    print("\n⚠️  IMPORTANT: Use mitch@nine80.ai account!")
    print("\nStarting OAuth flow...")
    
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secrets_path, SCOPES
    )
    
    # Get the authorization URL
    flow.redirect_uri = 'http://localhost:8080/'
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        login_hint='mitch@nine80.ai',  # Suggest the right account
        prompt='select_account'  # Force account selection
    )
    
    print("\n📋 INSTRUCTIONS:")
    print("1. Open an INCOGNITO/PRIVATE browser window")
    print("2. Copy and paste this URL:")
    print("\n" + "=" * 60)
    print(auth_url)
    print("=" * 60)
    print("\n3. Log in with mitch@nine80.ai")
    print("4. Grant access to Google Drive")
    print("5. You'll be redirected to a localhost page")
    print("\nOpening browser now (you can also copy the URL above)...")
    
    # Try to open in default browser
    webbrowser.open(auth_url)
    
    # Run the local server to handle the callback
    creds = flow.run_local_server(
        port=8080,
        authorization_prompt_message='',  # We already printed instructions
        success_message='✅ Authentication successful! You can close this window.',
        open_browser=False  # Don't open again since we did it manually
    )
    
    # Save the credentials
    with open(token_path, 'wb') as token:
        pickle.dump(creds, token)
        print(f"\n✓ Token saved to {token_path}")
    
    print("\n✅ Google Drive OAuth setup complete!")
    print("You can now run the document vectorizer.")
    return True

if __name__ == '__main__':
    setup_oauth()