#!/usr/bin/env python3
"""Update metadata for all files without reprocessing everything."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.google_drive import GoogleDriveClient
from config.settings import settings
from supabase import create_client
from datetime import datetime
import json

def main():
    """Update metadata for all files."""
    
    # Initialize
    print("Initializing...")
    drive_client = GoogleDriveClient()
    supabase = create_client(settings.supabase_url, settings.supabase_key)
    
    # Get ALL files
    print(f"Fetching all files from folder {settings.google_drive_folder_id}...")
    all_files = drive_client.list_files(
        folder_id=settings.google_drive_folder_id,
        recursive=True
    )
    
    print(f"Found {len(all_files)} total files")
    
    # Filter out folders and process each file's metadata
    files_processed = 0
    for file_info in all_files:
        if file_info.get('mimeType') == 'application/vnd.google-apps.folder':
            continue
            
        try:
            # Prepare metadata record
            metadata_record = {
                'id': file_info['id'],
                'title': file_info['name'],
                'url': file_info.get('webViewLink', ''),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Upsert to metadata table
            response = supabase.table('document_metadata').upsert(metadata_record).execute()
            files_processed += 1
            print(f"✓ Updated metadata for: {file_info['name']}")
            
        except Exception as e:
            print(f"✗ Error updating metadata for {file_info['name']}: {e}")
    
    print(f"\nCompleted! Updated metadata for {files_processed} files.")

if __name__ == "__main__":
    main()