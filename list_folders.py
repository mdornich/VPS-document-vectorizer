#!/usr/bin/env python3
"""List all Google Drive folders accessible to the account"""

import pickle
from pathlib import Path
from googleapiclient.discovery import build

# Load token
with open('config/token.json', 'rb') as f:
    creds = pickle.load(f)

# Build service
service = build('drive', 'v3', credentials=creds)

print("Listing your Google Drive folders:")
print("=" * 60)

# Query for folders only
query = "mimeType='application/vnd.google-apps.folder' and trashed = false"
results = service.files().list(
    q=query,
    pageSize=20,
    fields="files(id, name, createdTime)",
    orderBy="modifiedTime desc"
).execute()

folders = results.get('files', [])

if not folders:
    print("No folders found.")
else:
    print(f"Found {len(folders)} folders (showing most recent):\n")
    for folder in folders:
        print(f"📁 {folder['name']}")
        print(f"   ID: {folder['id']}")
        print()
        
    print("\nTo use a different folder, update GOOGLE_DRIVE_FOLDER_ID in .env")
    print("with one of the IDs above, then restart the Docker container.")