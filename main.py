#!/usr/bin/env python3
"""
Document Vectorizer - Main Application
Monitors Google Drive for new/updated documents and vectorizes them into Supabase.
"""

import sys
import time
import signal
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import argparse
from pathlib import Path

import schedule
import structlog
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from config.settings import settings
from src.logger import setup_logging
from src.google_drive import GoogleDriveClient
from src.document_extractor import DocumentExtractor
from src.vector_store import VectorStore

# Setup logging
logger = setup_logging()
console = Console()


class DocumentVectorizer:
    """Main application orchestrator."""
    
    def __init__(self):
        self.running = True
        self.google_drive = None
        self.extractor = DocumentExtractor()
        self.vector_store = VectorStore()
        self.processed_count = 0
        self.error_count = 0
        self.last_run = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def initialize(self):
        """Initialize all services."""
        try:
            console.print("[bold blue]Initializing Document Vectorizer...[/bold blue]")
            
            # Initialize Google Drive client
            self.google_drive = GoogleDriveClient()
            
            # Test connections
            self._test_connections()
            
            console.print("[bold green]✓ Initialization complete![/bold green]")
            return True
            
        except Exception as e:
            console.print(f"[bold red]✗ Initialization failed: {e}[/bold red]")
            logger.error(f"Initialization error: {e}")
            return False
    
    def _test_connections(self):
        """Test connections to all services."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # Test Google Drive
            task = progress.add_task("Testing Google Drive connection...", total=1)
            try:
                files = self.google_drive.list_files(limit=1)
                progress.update(task, completed=1)
                logger.info("Google Drive connection successful")
            except Exception as e:
                raise Exception(f"Google Drive connection failed: {e}")
            
            # Test Supabase
            task = progress.add_task("Testing Supabase connection...", total=1)
            try:
                stats = self.vector_store.get_document_stats()
                progress.update(task, completed=1)
                logger.info(f"Supabase connection successful. Stats: {stats}")
            except Exception as e:
                raise Exception(f"Supabase connection failed: {e}")
    
    def process_file(self, file_metadata: Dict[str, Any]) -> bool:
        """
        Process a single file.
        
        Args:
            file_metadata: Google Drive file metadata
        
        Returns:
            True if successful, False otherwise
        """
        file_id = file_metadata['id']
        file_name = file_metadata['name']
        
        try:
            logger.info(f"Processing file: {file_name}")
            
            # Download file
            console.print(f"  📥 Downloading: {file_name}")
            file_content = self.google_drive.download_file(file_id, file_metadata)
            
            # Extract content
            console.print(f"  📄 Extracting content...")
            extracted = self.extractor.extract(file_content, file_metadata)
            
            if extracted.get('type') == 'error':
                console.print(f"  [yellow]⚠ Extraction failed: {extracted.get('error')}[/yellow]")
                return False
            
            # Vectorize and store
            console.print(f"  🔄 Vectorizing and storing...")
            result = self.vector_store.process_document(extracted, file_metadata)
            
            # Mark file as processed in the tracker
            self.google_drive.file_tracker.mark_processed(
                file_id, 
                file_metadata.get('modifiedTime', '')
            )
            
            console.print(f"  [green]✓ Complete: {result}[/green]")
            return True
            
        except Exception as e:
            console.print(f"  [red]✗ Error: {e}[/red]")
            logger.error(f"Error processing {file_name}: {e}")
            return False
    
    def run_sync(self):
        """Run a single synchronization cycle."""
        try:
            console.print(f"\n[bold cyan]Starting sync at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/bold cyan]")
            
            # Get new/updated files
            files = self.google_drive.check_for_updates()
            
            if not files:
                console.print("[dim]No new or updated files found.[/dim]")
                return
            
            console.print(f"Found [bold]{len(files)}[/bold] file(s) to process\n")
            
            # Process each file
            success_count = 0
            error_count = 0
            
            for file in files:
                if not self.running:
                    break
                
                success = self.process_file(file)
                if success:
                    success_count += 1
                    self.processed_count += 1
                else:
                    error_count += 1
                    self.error_count += 1
            
            # Summary
            console.print(f"\n[bold]Sync Complete:[/bold]")
            console.print(f"  ✓ Processed: {success_count}")
            if error_count > 0:
                console.print(f"  ✗ Errors: {error_count}")
            
            self.last_run = datetime.now()
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            console.print(f"[bold red]Sync failed: {e}[/bold red]")
    
    def update_polling_schedule(self, new_interval: int) -> bool:
        """Update the polling schedule with a new interval."""
        try:
            # Clear existing scheduled jobs for this instance
            schedule.clear()
            
            # Update settings
            if settings.update_runtime_setting('polling_interval', new_interval):
                # Schedule new job with updated interval
                schedule.every(new_interval).seconds.do(self.run_sync)
                
                console.print(f"[bold green]Polling interval updated to {new_interval}s[/bold green]")
                logger.info(f"Polling schedule updated to {new_interval}s interval")
                return True
            else:
                # Fallback: recreate with current settings if runtime update failed
                schedule.every(settings.polling_interval).seconds.do(self.run_sync)
                logger.error(f"Failed to persist new polling interval {new_interval}s")
                return False
                
        except Exception as e:
            logger.error(f"Error updating polling schedule: {e}")
            # Ensure we have a schedule even if update failed
            try:
                schedule.clear()
                schedule.every(settings.polling_interval).seconds.do(self.run_sync)
            except:
                pass
            return False
    
    def get_current_polling_interval(self) -> int:
        """Get the current polling interval."""
        return settings.polling_interval
    
    def run_continuous(self):
        """Run in continuous monitoring mode."""
        console.print(f"[bold magenta]Starting continuous monitoring (interval: {settings.polling_interval}s)[/bold magenta]")
        
        # Schedule periodic syncs
        schedule.every(settings.polling_interval).seconds.do(self.run_sync)
        
        # Run initial sync
        self.run_sync()
        
        # Main loop
        while self.running:
            schedule.run_pending()
            time.sleep(1)
            
            # Show status every minute
            if int(time.time()) % 60 == 0:
                self._show_status()
        
        console.print("\n[bold yellow]Monitoring stopped.[/bold yellow]")
    
    def _show_status(self):
        """Display current status."""
        if self.last_run:
            time_since = datetime.now() - self.last_run
            next_run = self.last_run + timedelta(seconds=settings.polling_interval)
            time_until = next_run - datetime.now()
            
            status = f"Last sync: {time_since.seconds}s ago | Next in: {time_until.seconds}s | "
            status += f"Processed: {self.processed_count} | Errors: {self.error_count}"
            console.print(f"[dim]{status}[/dim]", end='\r')
    
    def show_stats(self):
        """Display statistics about stored documents."""
        try:
            stats = self.vector_store.get_document_stats()
            
            table = Table(title="Document Storage Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Documents", str(stats['total_documents']))
            table.add_row("Total Vectors", str(stats['total_vectors']))
            table.add_row("Avg Vectors/Doc", f"{stats['avg_vectors_per_doc']:.1f}")
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error getting stats: {e}[/red]")
    
    def setup_oauth(self):
        """Run OAuth setup flow for Google Drive."""
        console.print("[bold]Setting up Google Drive OAuth...[/bold]")
        console.print("1. Go to https://console.cloud.google.com/")
        console.print("2. Create a new project or select existing")
        console.print("3. Enable Google Drive API")
        console.print("4. Create OAuth 2.0 credentials")
        console.print("5. Download and save as 'config/client_secrets.json'")
        console.print("\nPress Enter when ready...")
        input()
        
        try:
            self.google_drive = GoogleDriveClient()
            self.google_drive.authenticate_oauth()
            console.print("[green]✓ OAuth setup complete![/green]")
        except Exception as e:
            console.print(f"[red]OAuth setup failed: {e}[/red]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Document Vectorizer - Sync Google Drive to Supabase vectors"
    )
    parser.add_argument(
        '--mode',
        choices=['once', 'continuous', 'stats', 'setup-oauth'],
        default='continuous',
        help='Run mode (default: continuous)'
    )
    parser.add_argument(
        '--folder-id',
        help='Override Google Drive folder ID'
    )
    parser.add_argument(
        '--interval',
        type=int,
        help='Override polling interval in seconds'
    )
    
    args = parser.parse_args()
    
    # Override settings if provided
    if args.folder_id:
        settings.google_drive_folder_id = args.folder_id
    if args.interval:
        settings.polling_interval = args.interval
    
    # Create application instance
    app = DocumentVectorizer()
    
    # Handle different modes
    if args.mode == 'setup-oauth':
        app.setup_oauth()
        return
    
    if args.mode == 'stats':
        if app.initialize():
            app.show_stats()
        return
    
    # Initialize for processing modes
    if not app.initialize():
        sys.exit(1)
    
    try:
        if args.mode == 'once':
            app.run_sync()
        else:  # continuous
            app.run_continuous()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Fatal error: {e}[/bold red]")
        logger.exception("Fatal error")
        sys.exit(1)
    finally:
        console.print(f"\n[bold]Final Statistics:[/bold]")
        console.print(f"  Total Processed: {app.processed_count}")
        console.print(f"  Total Errors: {app.error_count}")


if __name__ == "__main__":
    main()