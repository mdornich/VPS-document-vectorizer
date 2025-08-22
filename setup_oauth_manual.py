#!/usr/bin/env python3
"""
Manual OAuth setup - copy URL to incognito window
"""

import os
import pickle
from pathlib import Path
import socket
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class CallbackHandler(BaseHTTPRequestHandler):
    """Handler for OAuth callback"""
    def do_GET(self):
        """Handle the OAuth callback"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Extract the authorization code from the URL
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            self.server.auth_code = params['code'][0]
            message = """
            <html>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1 style="color: green;">✅ Authentication Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """
        else:
            message = """
            <html>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1 style="color: red;">❌ Authentication Failed</h1>
                <p>Please try again.</p>
            </body>
            </html>
            """
        
        self.wfile.write(message.encode())
    
    def log_message(self, format, *args):
        """Suppress log messages"""
        pass

def setup_oauth_manual():
    """Run OAuth flow with manual URL entry"""
    token_path = 'config/token.json'
    client_secrets_path = 'config/client_secrets.json'
    
    Path('config').mkdir(exist_ok=True)
    
    if not os.path.exists(client_secrets_path):
        print(f"❌ Error: {client_secrets_path} not found!")
        return False
    
    print("\n" + "=" * 70)
    print("🔐 Google Drive OAuth Setup - MANUAL MODE")
    print("=" * 70)
    
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secrets_path, SCOPES
    )
    
    # Use a specific port
    port = 8080
    redirect_uri = f'http://localhost:{port}/'
    flow.redirect_uri = redirect_uri
    
    # Generate authorization URL with account hint
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        login_hint='mitch@nine80.ai',
        prompt='select_account'
    )
    
    print("\n📋 INSTRUCTIONS:\n")
    print("1. Open a NEW INCOGNITO/PRIVATE browser window")
    print("   • Chrome: Cmd+Shift+N")
    print("   • Safari: Cmd+Shift+N")
    print("   • Firefox: Cmd+Shift+P")
    print("\n2. Copy and paste this ENTIRE URL into the incognito window:\n")
    print("─" * 70)
    print(auth_url)
    print("─" * 70)
    print("\n3. Sign in with: mitch@nine80.ai")
    print("4. Grant access to Google Drive")
    print("5. You'll be redirected back here automatically")
    print("\n⏳ Waiting for authentication...")
    
    # Start local server to receive the callback
    server = HTTPServer(('localhost', port), CallbackHandler)
    server.auth_code = None
    
    # Handle one request (the callback)
    server.handle_request()
    
    if server.auth_code:
        # Exchange the authorization code for credentials
        flow.fetch_token(code=server.auth_code)
        creds = flow.credentials
        
        # Save the credentials
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
        
        print("\n✅ SUCCESS! Token saved to config/token.json")
        print("You can now run the document vectorizer with Docker!")
        return True
    else:
        print("\n❌ Authentication failed or was cancelled.")
        return False

if __name__ == '__main__':
    setup_oauth_manual()