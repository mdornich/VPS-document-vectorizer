#!/usr/bin/env python3
"""
Convert OAuth token to pickle format for the document vectorizer app
"""

import json
import pickle
import sys
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials

def convert_token(token_file_path, client_secrets_path='config/client_secrets.json', output_path='config/token.json'):
    """
    Convert a JSON OAuth token to pickle format.
    
    Args:
        token_file_path: Path to the OAuth token JSON file
        client_secrets_path: Path to the client secrets JSON file
        output_path: Path where to save the pickle token
    """
    try:
        # Read the OAuth token
        with open(token_file_path, 'r') as f:
            token_data = json.load(f)

        # Read client secrets to get client ID and secret
        with open(client_secrets_path, 'r') as f:
            client_config = json.load(f)
            client_id = client_config['installed']['client_id']
            client_secret = client_config['installed']['client_secret']

        # Create Google credentials object
        creds = Credentials(
            token=token_data['access_token'],
            refresh_token=token_data['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret,
            scopes=[token_data['scope']]
        )

        # Save as pickle for our app
        with open(output_path, 'wb') as f:
            pickle.dump(creds, f)

        print("✅ Successfully converted token!")
        print(f"Token saved to: {output_path}")
        print("\nYou can now run the document vectorizer!")
        
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        print("Make sure the token file and client secrets exist.")
        sys.exit(1)
    except KeyError as e:
        print(f"❌ Missing required field in token: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error converting token: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_token_to_pickle.py <token_file_path> [client_secrets_path] [output_path]")
        print("Example: python convert_token_to_pickle.py /path/to/token.json")
        sys.exit(1)
    
    token_file = sys.argv[1]
    client_secrets = sys.argv[2] if len(sys.argv) > 2 else 'config/client_secrets.json'
    output = sys.argv[3] if len(sys.argv) > 3 else 'config/token.json'
    
    convert_token(token_file, client_secrets, output)