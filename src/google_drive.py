import os
import io
import json
import pickle
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from src.file_tracker import FileTracker

logger = structlog.get_logger()

# Rate limiting for Google Drive API
class APIRateLimiter:
    """Simple rate limiter for Google Drive API calls."""
    
    def __init__(self, calls_per_second: float = 10.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0.0
    
    def wait_if_needed(self):
        """Wait if we need to throttle the API call."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.min_interval:
            sleep_time = self.min_interval - time_since_last_call
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()

# Global rate limiter instance
api_limiter = APIRateLimiter(calls_per_second=10.0)  # Conservative rate

# Google Drive MIME type mappings
MIME_TYPE_CONVERSIONS = {
    'application/vnd.google-apps.document': 'text/plain',
    'application/vnd.google-apps.spreadsheet': 'text/csv',
    'application/vnd.google-apps.presentation': 'text/plain',
}

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


class GoogleDriveClient:
    """Client for interacting with Google Drive API."""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self._last_check_time = {}
        self.file_tracker = FileTracker()  # Use persistent file tracker
        
        # File listing cache to reduce API calls
        self._file_cache = {}
        self._cache_duration = timedelta(minutes=2)  # Cache for 2 minutes
        self._last_cache_time = {}
        
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Drive service with authentication."""
        try:
            # Try service account first (preferred for production)
            if os.path.exists(settings.google_credentials_path):
                self.credentials = ServiceCredentials.from_service_account_file(
                    settings.google_credentials_path,
                    scopes=SCOPES
                )
                logger.info("Using service account credentials")
            # Fall back to OAuth2 flow
            elif os.path.exists(settings.google_token_path):
                with open(settings.google_token_path, 'rb') as token:
                    self.credentials = pickle.load(token)
                    logger.info("Using cached OAuth2 token")
            
            # Refresh token if needed
            if self.credentials and hasattr(self.credentials, 'expired') and self.credentials.expired:
                if hasattr(self.credentials, 'refresh_token'):
                    self.credentials.refresh(Request())
                    self._save_credentials()
            
            # Build service
            if self.credentials:
                self.service = build('drive', 'v3', credentials=self.credentials)
                logger.info("Google Drive service initialized successfully")
            else:
                raise ValueError("No valid credentials found")
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    def authenticate_oauth(self):
        """Perform OAuth2 authentication flow (for initial setup)."""
        flow = InstalledAppFlow.from_client_secrets_file(
            'config/client_secrets.json', SCOPES
        )
        self.credentials = flow.run_local_server(port=0)
        self._save_credentials()
        self._initialize_service()
    
    def _save_credentials(self):
        """Save credentials to token file."""
        try:
            with open(settings.google_token_path, 'wb') as token:
                pickle.dump(self.credentials, token)
        except OSError as e:
            logger.warning(f"Could not save token (may be read-only filesystem): {e}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._last_cache_time:
            return False
        
        time_elapsed = datetime.utcnow() - self._last_cache_time[cache_key]
        return time_elapsed < self._cache_duration
    
    def _get_cache_key(self, folder_id: str, modified_after: Optional[datetime], recursive: bool) -> str:
        """Generate a cache key for file listings."""
        modified_str = modified_after.isoformat() if modified_after else "none"
        return f"{folder_id}:{modified_str}:{recursive}"
    
    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def list_files(
        self, 
        folder_id: Optional[str] = None,
        modified_after: Optional[datetime] = None,
        limit: Optional[int] = None,
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """
        List files in a Google Drive folder with caching and rate limiting.
        
        Args:
            folder_id: Google Drive folder ID
            modified_after: Only return files modified after this datetime
            limit: Maximum number of files to return
            recursive: Whether to include files from nested folders
        
        Returns:
            List of file metadata dictionaries
        """
        folder_id = folder_id or settings.google_drive_folder_id
        
        # Check cache first
        cache_key = self._get_cache_key(folder_id, modified_after, recursive)
        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached file listing for {folder_id}")
            cached_files = self._file_cache.get(cache_key, [])
            return cached_files[:limit] if limit else cached_files
        
        try:
            query_parts = [
                f"'{folder_id}' in parents",
                "trashed = false"
            ]
            
            if modified_after:
                # Format datetime for Google Drive API
                modified_str = modified_after.isoformat() + 'Z'
                query_parts.append(f"modifiedTime > '{modified_str}'")
            
            query = " and ".join(query_parts)
            
            results = []
            page_token = None
            
            while True:
                # Apply rate limiting
                api_limiter.wait_if_needed()
                
                response = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, size)",
                    pageToken=page_token,
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                
                files = response.get('files', [])
                
                # Separate folders from files
                folders = []
                for file in files:
                    if file.get('mimeType') == 'application/vnd.google-apps.folder':
                        folders.append(file)
                    else:
                        results.append(file)
                
                # Recursively process subfolders if enabled
                if recursive and folders:
                    for folder in folders:
                        logger.info(f"Processing nested folder: {folder['name']} (ID: {folder['id']})")
                        nested_files = self.list_files(
                            folder_id=folder['id'],
                            modified_after=modified_after,
                            recursive=True  # Continue recursion
                        )
                        results.extend(nested_files)
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                
                # Apply limit if specified
                if limit and len(results) >= limit:
                    results = results[:limit]
                    break
            
            # Cache the results
            self._file_cache[cache_key] = results
            self._last_cache_time[cache_key] = datetime.utcnow()
            
            logger.info(f"Found {len(results)} files in folder {folder_id} (recursive={recursive})")
            return results
            
        except HttpError as error:
            logger.error(f"Error listing files: {error}")
            raise
    
    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def download_file(self, file_id: str, file_metadata: Dict[str, Any]) -> bytes:
        """
        Download a file from Google Drive with rate limiting.
        
        Args:
            file_id: Google Drive file ID
            file_metadata: File metadata including mimeType
        
        Returns:
            File content as bytes
        """
        try:
            # Apply rate limiting before download
            api_limiter.wait_if_needed()
            
            mime_type = file_metadata.get('mimeType', '')
            
            # Handle Google Docs conversion
            if mime_type in MIME_TYPE_CONVERSIONS:
                export_mime_type = MIME_TYPE_CONVERSIONS[mime_type]
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime_type
                )
                logger.info(f"Exporting Google Doc {file_id} as {export_mime_type}")
            else:
                # Direct download for other files
                request = self.service.files().get_media(
                    fileId=file_id,
                    supportsAllDrives=True
                )
                logger.info(f"Downloading file {file_id} with type {mime_type}")
            
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")
            
            return file_content.getvalue()
            
        except HttpError as error:
            logger.error(f"Error downloading file {file_id}: {error}")
            raise
    
    def check_for_updates(self) -> List[Dict[str, Any]]:
        """
        Check for new or updated files since last check.
        Detects both new files and updated files regardless of when they were created.
        
        Returns:
            List of new/updated file metadata
        """
        folder_id = settings.google_drive_folder_id
        
        # Get ALL files in the folder (not filtered by date)
        all_files = self.list_files(folder_id, modified_after=None, recursive=True)
        
        # Use the file tracker to identify new or updated files
        new_files = self.file_tracker.get_new_or_updated_files(all_files)
        
        # Update last check time
        self._last_check_time[folder_id] = datetime.utcnow()
        
        if new_files:
            logger.info(f"Found {len(new_files)} new/updated files")
            # Note: Don't mark as processed here - let the main app do that after successful processing
        
        return new_files
    
    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get detailed metadata for a specific file."""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, webViewLink, modifiedTime, size, parents"
            ).execute()
            return file
        except HttpError as error:
            logger.error(f"Error getting file metadata for {file_id}: {error}")
            raise