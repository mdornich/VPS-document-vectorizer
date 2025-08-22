#!/usr/bin/env python3
"""
Document Vectorizer Web Dashboard
Provides monitoring and management interface for the document processing system.
"""

import os
import json
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import time

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import structlog
from config.settings import settings
from src.google_drive import GoogleDriveClient
from src.vector_store import VectorStore
from src.document_extractor import DocumentExtractor
from src.email_sender import send_error_alert, test_email
from main import DocumentVectorizer

# Setup logging
logger = structlog.get_logger()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
class AppState:
    def __init__(self):
        self.vectorizer = None
        self.processing_thread = None
        self.is_paused = False
        self.processing_queue = []
        self.processing_history = []
        self.error_log = []
        self.stats = {
            'total_processed': 0,
            'total_errors': 0,
            'last_sync': None,
            'uptime_start': datetime.now()
        }
        self.connections = {
            'google_drive': False,
            'supabase': False,
            'openai': False
        }
        
state = AppState()


# Background monitoring thread
def background_monitor():
    """Background thread for monitoring system status."""
    while True:
        try:
            # Check connections
            check_system_health()
            
            # Emit status update
            socketio.emit('status_update', get_system_status())
            
            time.sleep(5)  # Check every 5 seconds
        except Exception as e:
            logger.error(f"Monitor thread error: {e}")
            time.sleep(10)

def check_system_health():
    """Check health of all system components."""
    try:
        # Check Google Drive
        if state.vectorizer and state.vectorizer.google_drive:
            try:
                state.vectorizer.google_drive.list_files(limit=1)
                state.connections['google_drive'] = True
            except:
                state.connections['google_drive'] = False
        
        # Check Supabase
        if state.vectorizer and state.vectorizer.vector_store:
            try:
                state.vectorizer.vector_store.get_document_stats()
                state.connections['supabase'] = True
            except:
                state.connections['supabase'] = False
                
    except Exception as e:
        logger.error(f"Health check error: {e}")

def get_system_status() -> Dict[str, Any]:
    """Get current system status."""
    # Get processed count from file tracker if available
    processed_count = state.stats.get('total_processed', 0)
    if state.vectorizer and hasattr(state.vectorizer.google_drive, 'file_tracker'):
        tracker_stats = state.vectorizer.google_drive.file_tracker.get_stats()
        processed_count = tracker_stats.get('total_tracked', 0)
    
    return {
        'is_running': state.processing_thread and state.processing_thread.is_alive(),
        'is_paused': state.is_paused,
        'connections': state.connections,
        'stats': {
            **state.stats,
            'total_processed': processed_count
        },
        'queue_length': len(state.processing_queue),
        'recent_errors': state.error_log[-5:] if state.error_log else []
    }

# Routes
@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')

@app.route('/api/health')
def api_health():
    """Health check endpoint for monitoring."""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {}
    }
    
    # Check each service
    try:
        if state.vectorizer:
            # Check Google Drive
            try:
                state.vectorizer.google_drive.service.files().list(
                    pageSize=1, fields="files(id)"
                ).execute()
                health_status['services']['google_drive'] = 'healthy'
            except:
                health_status['services']['google_drive'] = 'unhealthy'
                health_status['status'] = 'degraded'
            
            # Check Supabase
            try:
                state.vectorizer.vector_store.supabase.table(
                    settings.supabase_metadata_table
                ).select('id').limit(1).execute()
                health_status['services']['supabase'] = 'healthy'
            except:
                health_status['services']['supabase'] = 'unhealthy'
                health_status['status'] = 'degraded'
        else:
            health_status['status'] = 'initializing'
            
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['error'] = str(e)
        
    # Return appropriate status code
    status_code = 200 if health_status['status'] in ['healthy', 'initializing'] else 503
    return jsonify(health_status), status_code

@app.route('/api/status')
def api_status():
    """Get system status."""
    return jsonify(get_system_status())

@app.route('/api/stats')
def api_stats():
    """Get processing statistics."""
    if not state.vectorizer:
        return jsonify({'error': 'System not initialized'}), 503
    
    try:
        vector_stats = state.vectorizer.vector_store.get_document_stats()
        
        # Get file type breakdown
        file_types = {}
        for item in state.processing_history:
            file_type = item.get('file_type', 'unknown')
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        return jsonify({
            'vector_stats': vector_stats,
            'processing_stats': state.stats,
            'file_types': file_types,
            'history_count': len(state.processing_history),
            'error_count': len(state.error_log)
        })
    except Exception as e:
        logger.error(f"Stats API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/folders')
def api_folders():
    """Get monitored folders and their file counts."""
    if not state.vectorizer:
        return jsonify({'error': 'System not initialized'}), 503
    
    try:
        # Get the main folder ID
        main_folder_id = settings.google_drive_folder_id
        
        # Get all files and organize by folder
        all_files = state.vectorizer.google_drive.list_files(
            main_folder_id, 
            modified_after=None, 
            recursive=False
        )
        
        # Get folders (not files)
        folders_response = state.vectorizer.google_drive.service.files().list(
            q=f"'{main_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name, modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = []
        
        # Add main folder
        main_folder_info = {
            'id': main_folder_id,
            'name': 'Main Folder (Root)',
            'file_count': len(all_files),
            'subfolders': []
        }
        
        # Process each subfolder
        for folder in folders_response.get('files', []):
            # Get file count in this folder
            folder_files = state.vectorizer.google_drive.list_files(
                folder['id'], 
                modified_after=None,
                recursive=False
            )
            
            # Check for nested folders
            nested_folders_response = state.vectorizer.google_drive.service.files().list(
                q=f"'{folder['id']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            folder_info = {
                'id': folder['id'],
                'name': folder['name'],
                'file_count': len(folder_files),
                'has_subfolders': len(nested_folders_response.get('files', [])) > 0,
                'modified_time': folder.get('modifiedTime', '')
            }
            main_folder_info['subfolders'].append(folder_info)
        
        # Sort folders by name
        main_folder_info['subfolders'].sort(key=lambda x: x['name'])
        
        # Get total file count across all folders
        total_files = state.vectorizer.google_drive.list_files(
            main_folder_id,
            modified_after=None,
            recursive=True
        )
        
        return jsonify({
            'main_folder': main_folder_info,
            'total_files': len(total_files),
            'folder_count': len(main_folder_info['subfolders']) + 1
        })
        
    except Exception as e:
        logger.error(f"Folders API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def api_history():
    """Get processing history."""
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    history = state.processing_history[offset:offset+limit]
    return jsonify({
        'history': history,
        'total': len(state.processing_history),
        'limit': limit,
        'offset': offset
    })

@app.route('/api/errors')
def api_errors():
    """Get error log."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({
        'errors': state.error_log[-limit:],
        'total': len(state.error_log)
    })

@app.route('/api/control/start', methods=['POST'])
def api_start():
    """Start the monitoring system."""
    if state.processing_thread and state.processing_thread.is_alive():
        return jsonify({'status': 'already_running'})
    
    try:
        # Initialize vectorizer if needed
        if not state.vectorizer:
            state.vectorizer = DocumentVectorizer()
            if not state.vectorizer.initialize():
                return jsonify({'error': 'Failed to initialize system'}), 500
        
        # Start processing in background thread
        state.is_paused = False
        state.processing_thread = threading.Thread(
            target=state.vectorizer.run_continuous,
            daemon=True
        )
        state.processing_thread.start()
        
        return jsonify({'status': 'started'})
    except Exception as e:
        logger.error(f"Start error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/control/stop', methods=['POST'])
def api_stop():
    """Stop the monitoring system."""
    if state.vectorizer:
        state.vectorizer.running = False
    state.is_paused = True
    return jsonify({'status': 'stopped'})

@app.route('/api/control/pause', methods=['POST'])
def api_pause():
    """Pause processing."""
    state.is_paused = True
    return jsonify({'status': 'paused'})

@app.route('/api/control/resume', methods=['POST'])
def api_resume():
    """Resume processing."""
    state.is_paused = False
    return jsonify({'status': 'resumed'})

@app.route('/api/control/sync', methods=['POST'])
def api_manual_sync():
    """Trigger manual sync."""
    if not state.vectorizer:
        return jsonify({'error': 'System not initialized'}), 503
    
    try:
        # Run sync in background
        def run_sync():
            try:
                state.vectorizer.run_sync()
                state.stats['last_sync'] = datetime.now().isoformat()
                socketio.emit('sync_complete', {'time': datetime.now().isoformat()})
            except Exception as e:
                error_data = {
                    'time': datetime.now().isoformat(),
                    'error': str(e),
                    'type': 'manual_sync'
                }
                state.error_log.append(error_data)
                # Use the new email sender
                from src.email_sender import send_error_alert as send_alert
                send_alert(f"Manual sync failed: {e}", error_data)
                socketio.emit('sync_error', error_data)
        
        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()
        
        return jsonify({'status': 'sync_started'})
    except Exception as e:
        logger.error(f"Manual sync error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/control/reset-tracker', methods=['POST'])
def api_reset_tracker():
    """Reset file tracker (will reprocess all files)."""
    if not state.vectorizer:
        return jsonify({'error': 'System not initialized'}), 503
    
    try:
        # Clear the tracker file
        tracker_file = state.vectorizer.google_drive.file_tracker.tracker_file
        if tracker_file.exists():
            os.remove(tracker_file)
        
        # Reinitialize tracker
        state.vectorizer.google_drive.file_tracker.__init__()
        
        return jsonify({'status': 'tracker_reset'})
    except Exception as e:
        logger.error(f"Reset tracker error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/control/test-alert', methods=['POST'])
def api_test_alert():
    """Test the email alert system."""
    try:
        # Use the new simple email system
        success = test_email()
        
        if success:
            # Add to log
            state.error_log.append({
                'time': datetime.now().isoformat(),
                'error': 'Test Alert: Email system working correctly',
                'type': 'test'
            })
            
            # Emit to websocket
            socketio.emit('alert_sent', {
                'message': 'Test alert sent',
                'email': 'admin@stablemischief.ai'
            })
            
            return jsonify({
                'status': 'alert_sent',
                'email': 'admin@stablemischief.ai',
                'email_configured': True,
                'message': 'Email sent successfully via Gmail SMTP'
            })
        else:
            return jsonify({
                'status': 'failed',
                'email': 'admin@stablemischief.ai',
                'email_configured': False,
                'message': 'Failed to send email - check logs'
            }), 500
            
    except Exception as e:
        logger.error(f"Test alert error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search for similar documents."""
    if not state.vectorizer:
        return jsonify({'error': 'System not initialized'}), 503
    
    data = request.json
    query = data.get('query', '')
    k = data.get('k', 5)
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    try:
        results = state.vectorizer.vector_store.search_similar(query, k=k)
        return jsonify({'results': results})
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config')
def api_get_config():
    """Get current configuration."""
    try:
        from src.runtime_settings import runtime_settings
        
        config_data = {
            'polling_interval': settings.polling_interval,
            'chunk_size': settings.chunk_size,
            'chunk_overlap': settings.chunk_overlap,
            'max_retries': settings.max_retries,
            'batch_size': settings.batch_size,
            'google_drive_folder_id': settings.google_drive_folder_id,
            'alert_email': getattr(state, 'alert_email', ''),
            'runtime_overrides': runtime_settings.get_all(),
            'has_runtime_settings': len(runtime_settings.get_all()) > 0
        }
        
        return jsonify(config_data)
        
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        # Fallback to basic config
        return jsonify({
            'polling_interval': settings.polling_interval,
            'chunk_size': settings.chunk_size,
            'chunk_overlap': settings.chunk_overlap,
            'max_retries': settings.max_retries,
            'batch_size': settings.batch_size,
            'google_drive_folder_id': settings.google_drive_folder_id,
            'alert_email': getattr(state, 'alert_email', ''),
            'runtime_overrides': {},
            'has_runtime_settings': False
        })

@app.route('/api/config', methods=['POST'])
def api_update_config():
    """Update configuration with persistence."""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        updated_settings = []
        failed_settings = []
        schedule_updated = False
        
        # Handle polling interval specially since it needs schedule update
        if 'polling_interval' in data:
            new_interval = data['polling_interval']
            
            # Validate polling interval
            if not isinstance(new_interval, int) or new_interval < 30 or new_interval > 86400:
                return jsonify({
                    'status': 'error', 
                    'message': 'Polling interval must be between 30 and 86400 seconds'
                }), 400
            
            # Update schedule if vectorizer is running
            if state.vectorizer:
                if state.vectorizer.update_polling_schedule(new_interval):
                    updated_settings.append(f'polling_interval: {new_interval}s')
                    schedule_updated = True
                else:
                    failed_settings.append('polling_interval')
            else:
                # Just update the setting if vectorizer not running
                if settings.update_runtime_setting('polling_interval', new_interval):
                    updated_settings.append(f'polling_interval: {new_interval}s')
                else:
                    failed_settings.append('polling_interval')
        
        # Handle other settings
        other_settings = {
            'chunk_size': (int, 50, 2000),
            'chunk_overlap': (int, 0, 500),
            'max_retries': (int, 1, 10),
            'batch_size': (int, 1, 1000),
        }
        
        for setting_name, (setting_type, min_val, max_val) in other_settings.items():
            if setting_name in data:
                new_value = data[setting_name]
                
                # Validate type and range
                if not isinstance(new_value, setting_type) or new_value < min_val or new_value > max_val:
                    return jsonify({
                        'status': 'error',
                        'message': f'{setting_name} must be between {min_val} and {max_val}'
                    }), 400
                
                # Update setting
                if settings.update_runtime_setting(setting_name, new_value):
                    updated_settings.append(f'{setting_name}: {new_value}')
                else:
                    failed_settings.append(setting_name)
        
        # Handle alert_email (stored in state, not persisted)
        if 'alert_email' in data:
            state.alert_email = data['alert_email']
            updated_settings.append(f'alert_email: {data["alert_email"]}')
        
        # Prepare response
        response = {
            'status': 'success' if not failed_settings else 'partial_success',
            'updated': updated_settings,
            'schedule_updated': schedule_updated
        }
        
        if failed_settings:
            response['failed'] = failed_settings
            response['message'] = f'Failed to update: {", ".join(failed_settings)}'
        
        # Log the update
        logger.info(f"Configuration updated: {updated_settings}")
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Configuration update failed: {str(e)}'
        }), 500

@app.route('/api/logs/download')
def api_download_logs():
    """Download logs as JSON."""
    logs = {
        'processing_history': state.processing_history,
        'error_log': state.error_log,
        'export_time': datetime.now().isoformat()
    }
    
    # Create temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(logs, f, indent=2)
        temp_path = f.name
    
    return send_file(
        temp_path,
        as_attachment=True,
        download_name=f'vectorizer_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    emit('connected', {'status': 'connected'})
    emit('status_update', get_system_status())

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# Initialize monitoring on startup
def initialize_app():
    """Initialize the application."""
    global state
    
    try:
        # Initialize vectorizer
        state.vectorizer = DocumentVectorizer()
        if state.vectorizer.initialize():
            logger.info("Vectorizer initialized successfully")
            check_system_health()
        else:
            logger.error("Failed to initialize vectorizer")
    except Exception as e:
        logger.error(f"Initialization error: {e}")
    
    # Start background monitor
    monitor_thread = threading.Thread(target=background_monitor, daemon=True)
    monitor_thread.start()

if __name__ == '__main__':
    initialize_app()
    socketio.run(app, debug=False, host='0.0.0.0', port=5555, allow_unsafe_werkzeug=True)