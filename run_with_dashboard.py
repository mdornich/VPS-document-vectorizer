#!/usr/bin/env python3
"""
Run both the document vectorizer and web dashboard together.
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

def run_services():
    """Run both backend and frontend services."""
    processes = []
    
    try:
        # Start the main vectorizer in background mode
        print("Starting Document Vectorizer backend...")
        vectorizer_process = subprocess.Popen(
            [sys.executable, 'main.py', '--mode', 'continuous'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(vectorizer_process)
        
        # Give the backend a moment to initialize
        time.sleep(3)
        
        # Start the web dashboard
        print("Starting Web Dashboard...")
        dashboard_process = subprocess.Popen(
            [sys.executable, 'web_app.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes.append(dashboard_process)
        
        print("\n" + "="*50)
        print("Document Vectorizer is running!")
        print("Dashboard URL: http://localhost:5555")
        print("Press Ctrl+C to stop all services")
        print("="*50 + "\n")
        
        # Wait for processes
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"Process {p.pid} terminated unexpectedly")
                    raise KeyboardInterrupt
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down services...")
        for p in processes:
            p.terminate()
        
        # Give processes time to terminate gracefully
        time.sleep(2)
        
        # Force kill if still running
        for p in processes:
            if p.poll() is None:
                p.kill()
        
        print("All services stopped.")

if __name__ == "__main__":
    run_services()