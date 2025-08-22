#!/bin/bash
# Docker entrypoint script for Document Vectorizer

echo "Starting Document Vectorizer..."

# Check if this is the first run
if [ ! -f /tmp/.vectorizer_initialized ]; then
    echo "First run detected - processing any existing files..."
    python main.py --mode once
    touch /tmp/.vectorizer_initialized
    echo "Initial processing complete!"
fi

# Start both the backend processor and web dashboard
echo "Starting backend processor and web dashboard..."

# Start the backend in background
python main.py --mode continuous &
BACKEND_PID=$!

# Give backend time to initialize
sleep 5

# Start the web dashboard
python web_app.py &
DASHBOARD_PID=$!

echo "=============================================="
echo "Document Vectorizer is running!"
echo "Dashboard available at: http://localhost:5555"
echo "=============================================="

# Function to handle shutdown
shutdown() {
    echo "Shutting down services..."
    kill $BACKEND_PID 2>/dev/null
    kill $DASHBOARD_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap shutdown SIGTERM SIGINT

# Wait for processes
wait $BACKEND_PID $DASHBOARD_PID