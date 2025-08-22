from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    # Google Drive settings
    google_drive_folder_id: str = Field(
        default="0ABmV46LxVYI6Uk9PVA",
        description="Google Drive folder ID to monitor"
    )
    google_credentials_path: str = Field(
        default="config/google_credentials.json",
        description="Path to Google service account credentials"
    )
    google_token_path: str = Field(
        default="config/token.json",
        description="Path to store Google OAuth token"
    )
    
    # Supabase settings
    supabase_url: str = Field(
        ...,
        description="Supabase project URL"
    )
    supabase_key: str = Field(
        ...,
        description="Supabase service key"
    )
    supabase_documents_table: str = Field(
        default="documents",
        description="Supabase table for document vectors"
    )
    supabase_metadata_table: str = Field(
        default="document_metadata",
        description="Supabase table for document metadata"
    )
    supabase_rows_table: str = Field(
        default="document_rows",
        description="Supabase table for structured data rows"
    )
    
    # OpenAI settings
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for embeddings"
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model to use"
    )
    
    # Processing settings
    chunk_size: int = Field(
        default=400,
        description="Size of text chunks for vectorization"
    )
    chunk_overlap: int = Field(
        default=50,
        description="Overlap between text chunks"
    )
    polling_interval: int = Field(
        default=300,  # Increased from 60s to 5 minutes for better stability
        description="Polling interval in seconds"
    )
    batch_size: int = Field(
        default=100,
        description="Batch size for vector insertions"
    )
    
    # Local storage
    temp_download_dir: str = Field(
        default="/tmp/document_downloads",
        description="Temporary directory for downloaded files"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_file: Optional[str] = Field(
        default="logs/document_vectorizer.log",
        description="Log file path"
    )
    
    # Production settings
    enable_monitoring: bool = Field(
        default=False,
        description="Enable production monitoring"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retries for failed operations"
    )
    retry_delay: int = Field(
        default=5,
        description="Delay between retries in seconds"
    )
    
    # Email alerts
    sendgrid_api_key: Optional[str] = Field(
        default=None,
        description="SendGrid API key for email alerts"
    )
    alert_email: str = Field(
        default="admin@stablemischief.ai",
        description="Email address for alerts"
    )
    
    # SMTP settings for email alerts
    smtp_host: Optional[str] = Field(
        default=None,
        description="SMTP server hostname"
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port (587 for TLS, 465 for SSL)"
    )
    smtp_username: Optional[str] = Field(
        default=None,
        description="SMTP username/email"
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP password"
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS for SMTP connection"
    )
    smtp_from_email: Optional[str] = Field(
        default=None,
        description="From email address for alerts"
    )
    
    # Flask settings
    flask_secret_key: str = Field(
        default="change-this-in-production-to-random-string",
        description="Flask secret key for sessions"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        Path(self.temp_download_dir).mkdir(parents=True, exist_ok=True)
        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Apply runtime settings overrides
        self._apply_runtime_settings()
    
    def _apply_runtime_settings(self) -> None:
        """Apply runtime settings that override defaults/environment variables."""
        try:
            # Import here to avoid circular dependency
            from src.runtime_settings import runtime_settings
            
            # List of settings that can be overridden at runtime
            runtime_overrides = {
                'polling_interval': int,
                'chunk_size': int,
                'chunk_overlap': int,
                'max_retries': int,
                'batch_size': int,
                'log_level': str,
            }
            
            for setting_name, setting_type in runtime_overrides.items():
                if runtime_settings.has_setting(setting_name):
                    runtime_value = runtime_settings.get(setting_name)
                    try:
                        # Convert to appropriate type
                        typed_value = setting_type(runtime_value)
                        setattr(self, setting_name, typed_value)
                        # Don't log here to avoid circular logging during initialization
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Invalid runtime setting {setting_name}={runtime_value}: {e}")
                        
        except ImportError:
            # Runtime settings module not available, skip
            pass
        except Exception as e:
            print(f"Warning: Error applying runtime settings: {e}")
    
    def update_runtime_setting(self, key: str, value: any) -> bool:
        """Update a runtime setting and save it persistently."""
        try:
            from src.runtime_settings import runtime_settings
            
            # Validate the setting exists and type
            if not hasattr(self, key):
                return False
            
            # Set the runtime setting
            if runtime_settings.set(key, value):
                # Update the current instance
                setattr(self, key, value)
                return True
            return False
            
        except Exception as e:
            print(f"Error updating runtime setting {key}: {e}")
            return False


# Singleton instance
settings = Settings()