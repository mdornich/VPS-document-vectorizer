#!/usr/bin/env python3
"""Force reprocessing of all files in the Google Drive folder."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from src.google_drive import GoogleDriveClient
from src.document_extractor import DocumentExtractor
from src.vector_store import VectorStore
from config.settings import settings
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(colors=True)
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

def main():
    """Force reprocess all files."""
    
    # Initialize components
    logger.info("Initializing components...")
    drive_client = GoogleDriveClient()
    extractor = DocumentExtractor()
    vector_store = VectorStore()
    
    # Get ALL files (not just new ones)
    logger.info(f"Fetching all files from folder {settings.google_drive_folder_id}...")
    all_files = drive_client.list_files(
        folder_id=settings.google_drive_folder_id,
        recursive=True  # Include nested folders
    )
    
    logger.info(f"Found {len(all_files)} total files to process")
    
    # Process each file
    success_count = 0
    error_count = 0
    
    for file_info in all_files:
        file_name = file_info['name']
        file_id = file_info['id']
        mime_type = file_info.get('mimeType', '')
        
        # Skip folders
        if mime_type == 'application/vnd.google-apps.folder':
            logger.info(f"Skipping folder: {file_name}")
            continue
            
        try:
            logger.info(f"Processing: {file_name} (ID: {file_id})")
            
            # Download file
            logger.info(f"  Downloading...")
            content = drive_client.download_file(file_id, file_info)
            
            # Extract content
            logger.info(f"  Extracting...")
            extracted = extractor.extract(content, file_info)
            
            if extracted.get('type') == 'error':
                logger.warning(f"  Extraction failed: {extracted.get('error')}")
                error_count += 1
                continue
            
            # Vectorize and store
            logger.info(f"  Vectorizing and storing...")
            result = vector_store.process_document(extracted, file_info)
            
            logger.info(f"  ✓ Success: {result}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"  ✗ Error processing {file_name}: {e}")
            error_count += 1
    
    # Final summary
    logger.info("\n" + "="*60)
    logger.info(f"PROCESSING COMPLETE")
    logger.info(f"  Total files found: {len(all_files)}")
    logger.info(f"  Successfully processed: {success_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info("="*60)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    main()