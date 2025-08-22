#!/usr/bin/env python3
"""
Standalone OAuth setup script for Google Drive authentication
"""

import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def setup_oauth():
    """Run OAuth flow to generate token.json"""
    creds = None
    token_path = 'config/token.json'
    client_secrets_path = 'config/client_secrets.json'
    
    # Create config directory if it doesn't exist
    Path('config').mkdir(exist_ok=True)
    
    # Check if token already exists
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
            print(f"✓ Found existing token at {token_path}")
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets_path):
                print(f"❌ Error: {client_secrets_path} not found!")
                return False
                
            print("Starting OAuth flow...")
            print("A browser window will open for authentication.")
            print("Please log in with your Google account and grant access to Google Drive.")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_path, SCOPES
            )
            # Force account selection
            creds = flow.run_local_server(
                port=0,
                authorization_prompt_message='Please log in with mitch@nine80.ai',
                success_message='Authentication successful! You can close this window.',
                open_browser=True
            )
            print("✓ Authentication successful!")
        
        # Save the credentials for the next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
            print(f"✓ Token saved to {token_path}")
    
    print("\n✅ Google Drive OAuth setup complete!")
    print("You can now run the document vectorizer with Docker or locally.")
    return True

if __name__ == '__main__':
    setup_oauth()