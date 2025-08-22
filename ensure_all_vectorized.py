#!/usr/bin/env python3
"""Ensure all files are vectorized - for production initialization."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.google_drive import GoogleDriveClient
from src.document_extractor import DocumentExtractor
from src.vector_store import VectorStore
from config.settings import settings
from supabase import create_client
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_and_vectorize_all():
    """Check which files need vectors and process them."""
    
    drive_client = GoogleDriveClient()
    extractor = DocumentExtractor()
    vector_store = VectorStore()
    supabase = create_client(settings.supabase_url, settings.supabase_key)
    
    # Get all files
    all_files = drive_client.list_files(recursive=True)
    
    # Check each file
    processed = 0
    for f in all_files:
        if f.get('mimeType') == 'application/vnd.google-apps.folder':
            continue
            
        try:
            # Check if already has vectors
            check = supabase.table('documents').select('id').eq('metadata->file_id', f['id']).limit(1).execute()
            
            if check.data:
                logger.info(f"✓ {f['name']} already has vectors")
                continue
            
            # Process the file
            logger.info(f"Processing: {f['name']}")
            content = drive_client.download_file(f['id'], f)
            extracted = extractor.extract(content, f)
            
            if extracted.get('type') != 'error':
                result = vector_store.process_document(extracted, f)
                logger.info(f"  Created {result.get('vectors_created', 0)} vectors")
                processed += 1
                time.sleep(1)  # Rate limiting
                
        except Exception as e:
            logger.error(f"Error with {f['name']}: {e}")
            continue
    
    return processed

if __name__ == "__main__":
    logger.info("Starting vectorization check...")
    processed = check_and_vectorize_all()
    logger.info(f"Processed {processed} files")