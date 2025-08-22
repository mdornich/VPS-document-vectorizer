"""
File tracking system to persist which files have been processed.
This ensures new folders/files are detected even if they have old modification dates.
"""

import json
import os
from pathlib import Path
from typing import Dict, Set, Optional, List
import structlog

logger = structlog.get_logger()


class FileTracker:
    """Track processed files persistently."""
    
    def __init__(self, tracker_file: str = "/app/data/tracker/processed_files.json"):
        """
        Initialize the file tracker.
        
        Args:
            tracker_file: Path to the JSON file storing processed file data
        """
        self.tracker_file = Path(tracker_file)
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed_files = self._load_tracker()
        # Track when we first saw a file in the watched folder
        self.first_seen_file = Path("/tmp/first_seen_files.json")
        self.first_seen = self._load_first_seen()
    
    def _load_tracker(self) -> Dict[str, str]:
        """Load the tracking data from disk."""
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} tracked files from {self.tracker_file}")
                    return data
            except Exception as e:
                logger.error(f"Error loading tracker file: {e}")
                return {}
        else:
            logger.info("No existing tracker file, starting fresh")
            return {}
    
    def _load_first_seen(self) -> Set[str]:
        """Load the first-seen data from disk."""
        if self.first_seen_file.exists():
            try:
                with open(self.first_seen_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} first-seen files")
                    return set(data)
            except Exception as e:
                logger.error(f"Error loading first-seen file: {e}")
                return set()
        else:
            logger.info("No existing first-seen file, starting fresh")
            return set()
    
    def _save_tracker(self):
        """Save the tracking data to disk."""
        try:
            with open(self.tracker_file, 'w') as f:
                json.dump(self.processed_files, f, indent=2)
            logger.debug(f"Saved {len(self.processed_files)} tracked files")
        except Exception as e:
            logger.error(f"Error saving tracker file: {e}")
    
    def _save_first_seen(self):
        """Save the first-seen data to disk."""
        try:
            with open(self.first_seen_file, 'w') as f:
                json.dump(list(self.first_seen), f, indent=2)
            logger.debug(f"Saved {len(self.first_seen)} first-seen files")
        except Exception as e:
            logger.error(f"Error saving first-seen file: {e}")
    
    def is_new_file(self, file_id: str) -> bool:
        """Check if a file is new (not previously seen)."""
        return file_id not in self.processed_files
    
    def is_updated_file(self, file_id: str, modified_time: str) -> bool:
        """Check if a file has been updated since last seen."""
        if file_id not in self.processed_files:
            return False
        return self.processed_files.get(file_id) != modified_time
    
    def mark_processed(self, file_id: str, modified_time: str):
        """Mark a file as processed."""
        self.processed_files[file_id] = modified_time
        self._save_tracker()
    
    def get_new_or_updated_files(self, all_files: list) -> list:
        """
        Given a list of all files, return only new or updated ones.
        
        This now tracks:
        1. Files never seen in this folder before (even if they're old)
        2. Files that have been updated since last processing
        
        Args:
            all_files: List of file dictionaries from Google Drive
            
        Returns:
            List of files that are new or have been updated
        """
        new_or_updated = []
        current_file_ids = {f['id'] for f in all_files}
        
        # Update our record of what files are currently in the folder
        newly_seen = current_file_ids - self.first_seen
        if newly_seen:
            logger.info(f"Found {len(newly_seen)} files newly added to the watched folder")
            self.first_seen.update(newly_seen)
            self._save_first_seen()
        
        for file in all_files:
            file_id = file['id']
            modified_time = file.get('modifiedTime', '')
            
            # Process if:
            # 1. We've never processed this file before (new to us)
            # 2. OR the file has been updated since we last processed it
            # 3. OR it's newly added to the folder (even if old)
            if self.is_new_file(file_id):
                logger.debug(f"New file (never processed): {file['name']} (ID: {file_id})")
                new_or_updated.append(file)
            elif self.is_updated_file(file_id, modified_time):
                logger.debug(f"Updated file: {file['name']} (ID: {file_id})")
                new_or_updated.append(file)
            elif file_id in newly_seen:
                logger.debug(f"Newly added to folder: {file['name']} (ID: {file_id})")
                new_or_updated.append(file)
        
        return new_or_updated
    
    def mark_files_processed(self, files: list):
        """Mark multiple files as processed."""
        for file in files:
            self.mark_processed(file['id'], file.get('modifiedTime', ''))
    
    def get_stats(self) -> dict:
        """Get statistics about tracked files."""
        return {
            'total_tracked': len(self.processed_files),
            'tracker_file': str(self.tracker_file)
        }