#!/usr/bin/env python3
"""
Safely clean up duplicate documents in Supabase that came from different folders.
This script will keep the most recent version of each document and delete older duplicates.
"""

import os
import sys
from datetime import datetime
from collections import defaultdict
from supabase import create_client, Client
import structlog

# Try to import settings from config
try:
    from config.settings import settings
    use_settings = True
except ImportError:
    from dotenv import load_dotenv
    load_dotenv()
    use_settings = False

# Setup logging
logger = structlog.get_logger()

def get_supabase_client():
    """Initialize Supabase client."""
    if use_settings:
        # Use settings from config module
        url = settings.supabase_url
        key = settings.supabase_key
    else:
        # Fall back to environment variables
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY')
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not found")
        sys.exit(1)
    
    return create_client(url, key)

def identify_duplicates(supabase: Client, dry_run=True):
    """
    Identify duplicate documents by title.
    Returns dict of title -> list of document records.
    """
    print("\n🔍 Fetching all documents from metadata table...")
    
    # Fetch all documents
    response = supabase.table('document_metadata').select('*').execute()
    documents = response.data
    
    print(f"Found {len(documents)} total documents")
    
    # Group by title
    docs_by_title = defaultdict(list)
    for doc in documents:
        title = doc.get('title', '').strip()
        if title:  # Ignore empty titles
            docs_by_title[title].append(doc)
    
    # Filter to only duplicates
    duplicates = {
        title: docs 
        for title, docs in docs_by_title.items() 
        if len(docs) > 1
    }
    
    print(f"Found {len(duplicates)} titles with duplicates")
    
    # Calculate total documents to be deleted
    total_to_delete = sum(len(docs) - 1 for docs in duplicates.values())
    print(f"Will delete {total_to_delete} duplicate documents (keeping {len(duplicates)} originals)")
    
    return duplicates

def cleanup_duplicates(supabase: Client, duplicates: dict, dry_run=True):
    """
    Remove duplicate documents, keeping the most recent one.
    """
    
    if not duplicates:
        print("No duplicates to clean up!")
        return
    
    print(f"\n{'🧪 DRY RUN MODE' if dry_run else '🗑️ DELETION MODE'}")
    print("=" * 50)
    
    deleted_count = 0
    error_count = 0
    
    for title, docs in duplicates.items():
        # Sort by created_at, keep the most recent
        docs_sorted = sorted(
            docs, 
            key=lambda x: x.get('created_at', ''), 
            reverse=True
        )
        
        keep = docs_sorted[0]
        delete = docs_sorted[1:]
        
        print(f"\n📄 Title: {title[:50]}...")
        print(f"   Keeping: ID {keep['id']} (created: {keep.get('created_at', 'unknown')})")
        
        for doc in delete:
            doc_id = doc['id']
            print(f"   Deleting: ID {doc_id} (created: {doc.get('created_at', 'unknown')})")
            
            if not dry_run:
                try:
                    # Delete from document_rows table first
                    try:
                        rows_resp = supabase.table('document_rows').delete().eq('dataset_id', doc_id).execute()
                        if rows_resp.data and len(rows_resp.data) > 0:
                            print(f"     ✓ Deleted {len(rows_resp.data)} rows")
                        else:
                            print(f"     ℹ️ No rows to delete")
                    except Exception as e:
                        print(f"     ⚠️ Could not delete rows: {str(e)[:50]}")
                    
                    # Delete from document_metadata table
                    try:
                        meta_resp = supabase.table('document_metadata').delete().eq('id', doc_id).execute()
                        if meta_resp.data:
                            print(f"     ✓ Deleted metadata")
                        else:
                            print(f"     ⚠️ No metadata deleted")
                    except Exception as e:
                        print(f"     ❌ Error deleting metadata: {str(e)[:50]}")
                        error_count += 1
                        continue
                    
                    # Note about vectors - they need special handling
                    print(f"     ℹ️ Note: Vector deletion requires manual cleanup in documents table")
                    
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"     ❌ Error deleting: {e}")
                    error_count += 1
    
    print("\n" + "=" * 50)
    if dry_run:
        print(f"DRY RUN COMPLETE - Would delete {deleted_count} documents")
        print("Run with --execute to actually delete duplicates")
    else:
        print(f"✅ CLEANUP COMPLETE")
        print(f"   Deleted: {deleted_count} documents")
        if error_count > 0:
            print(f"   Errors: {error_count} documents failed to delete")

def verify_cleanup(supabase: Client):
    """Verify the cleanup was successful."""
    print("\n🔍 Verifying cleanup...")
    
    # Check metadata table
    response = supabase.table('document_metadata').select('title', count='exact').execute()
    total_docs = response.count if hasattr(response, 'count') else len(response.data)
    
    # Check for remaining duplicates
    duplicates = identify_duplicates(supabase, dry_run=True)
    
    print(f"Total documents remaining: {total_docs}")
    print(f"Remaining duplicates: {len(duplicates)}")
    
    if duplicates:
        print("\n⚠️ Some duplicates remain:")
        for title in list(duplicates.keys())[:5]:
            print(f"  - {title}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up duplicate documents in Supabase')
    parser.add_argument(
        '--execute', 
        action='store_true', 
        help='Actually delete duplicates (default is dry run)'
    )
    parser.add_argument(
        '--verify-only', 
        action='store_true', 
        help='Only verify current state, don\'t delete anything'
    )
    parser.add_argument(
        '--no-confirm', 
        action='store_true', 
        help='Skip confirmation prompt (for non-interactive execution)'
    )
    
    args = parser.parse_args()
    
    # Initialize Supabase client
    print("🔌 Connecting to Supabase...")
    supabase = get_supabase_client()
    
    if args.verify_only:
        verify_cleanup(supabase)
    else:
        # Identify duplicates
        duplicates = identify_duplicates(supabase, dry_run=not args.execute)
        
        if duplicates:
            # Show some examples
            print("\n📋 Sample of duplicates found:")
            for i, (title, docs) in enumerate(list(duplicates.items())[:5]):
                print(f"{i+1}. '{title}' - {len(docs)} copies")
            
            if not args.execute:
                print("\n⚠️ This is a DRY RUN - no data will be deleted")
                print("Review the output above and run with --execute to delete duplicates")
                print("\nShowing cleanup plan...")
            else:
                # Skip confirmation if --no-confirm flag is set
                if not args.no_confirm:
                    print("\n⚠️ WARNING: This will permanently delete duplicate documents!")
                    print("Use --no-confirm flag to skip this prompt")
                    try:
                        response = input("Type 'DELETE' to confirm: ")
                        if response != 'DELETE':
                            print("Deletion cancelled")
                            return
                    except EOFError:
                        print("\nNon-interactive mode detected. Use --no-confirm flag to proceed")
                        return
                else:
                    print("\n🗑️ Proceeding with deletion (--no-confirm flag set)...")
            
            # Perform cleanup
            cleanup_duplicates(supabase, duplicates, dry_run=not args.execute)
            
            # Verify if we actually executed
            if args.execute:
                verify_cleanup(supabase)

if __name__ == "__main__":
    main()