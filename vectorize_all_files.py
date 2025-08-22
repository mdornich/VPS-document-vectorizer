#!/usr/bin/env python3
"""Vectorize all files that don't have vectors yet."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from src.google_drive import GoogleDriveClient
from src.document_extractor import DocumentExtractor
from src.vector_store import VectorStore
from config.settings import settings
from supabase import create_client
import time

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    """Vectorize all files missing vectors."""
    
    # Initialize components
    logger.info("🚀 Initializing components...")
    drive_client = GoogleDriveClient()
    extractor = DocumentExtractor()
    vector_store = VectorStore()
    supabase = create_client(settings.supabase_url, settings.supabase_key)
    
    # Get files that already have vectors
    logger.info("📊 Checking current vector status...")
    vectors = supabase.table('documents').select('metadata').execute()
    files_with_vectors = set()
    for v in vectors.data:
        if v.get('metadata') and v['metadata'].get('file_id'):
            files_with_vectors.add(v['metadata']['file_id'])
    
    logger.info(f"   Files already vectorized: {len(files_with_vectors)}")
    
    # Get all files from Google Drive
    logger.info("📁 Fetching all files from Google Drive...")
    all_files = drive_client.list_files(
        folder_id=settings.google_drive_folder_id,
        recursive=True
    )
    
    # Filter to files needing vectorization
    files_to_process = []
    for f in all_files:
        if (f.get('mimeType') != 'application/vnd.google-apps.folder' 
            and f['id'] not in files_with_vectors):
            files_to_process.append(f)
    
    logger.info(f"📝 Files needing vectorization: {len(files_to_process)}")
    
    if not files_to_process:
        logger.info("✅ All files already have vectors!")
        return
    
    # Process each file
    logger.info("\n" + "="*60)
    logger.info("Starting vectorization process...")
    logger.info("="*60 + "\n")
    
    success_count = 0
    error_count = 0
    
    for i, file_info in enumerate(files_to_process, 1):
        file_name = file_info['name']
        file_id = file_info['id']
        
        logger.info(f"[{i}/{len(files_to_process)}] Processing: {file_name}")
        
        try:
            # Download file
            logger.info("   📥 Downloading...")
            content = drive_client.download_file(file_id, file_info)
            
            # Extract content
            logger.info("   📄 Extracting content...")
            extracted = extractor.extract(content, file_info)
            
            if extracted.get('type') == 'error':
                logger.warning(f"   ⚠️  Extraction failed: {extracted.get('error')}")
                error_count += 1
                continue
            
            # Vectorize and store
            logger.info("   🔄 Creating vectors...")
            result = vector_store.process_document(extracted, file_info)
            
            vectors_created = result.get('vectors_created', 0)
            logger.info(f"   ✅ Success! Created {vectors_created} vector chunks")
            success_count += 1
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"   ❌ Error: {str(e)[:100]}")
            error_count += 1
            continue
    
    # Final summary
    logger.info("\n" + "="*60)
    logger.info("VECTORIZATION COMPLETE")
    logger.info("="*60)
    logger.info(f"✅ Successfully vectorized: {success_count} files")
    if error_count > 0:
        logger.info(f"❌ Errors: {error_count} files")
    logger.info(f"📊 Total vectors in database: Check Supabase dashboard")

if __name__ == "__main__":
    main()