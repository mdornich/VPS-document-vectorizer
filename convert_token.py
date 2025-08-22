#!/usr/bin/env python3
"""
Convert MCP token to pickle format for our app
"""

import json
import pickle
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials

# Read the MCP token
with open('/Users/mitchdornich/.npm/_npx/901beb8b1a496dd2/node_modules/.gdrive-server-credentials.json', 'r') as f:
    mcp_token = json.load(f)

# Read client secrets to get client ID and secret
with open('config/client_secrets.json', 'r') as f:
    client_config = json.load(f)
    client_id = client_config['installed']['client_id']
    client_secret = client_config['installed']['client_secret']

# Create Google credentials object
creds = Credentials(
    token=mcp_token['access_token'],
    refresh_token=mcp_token['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token',
    client_id=client_id,
    client_secret=client_secret,
    scopes=[mcp_token['scope']]
)

# Save as pickle for our app
with open('config/token.json', 'wb') as f:
    pickle.dump(creds, f)

print("✅ Successfully converted token!")
print("Token saved to: config/token.json")
print("\nYou can now run the document vectorizer!")