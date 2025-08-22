#!/bin/bash

# Stable Apps Document Vectorizer Deployment Script
# Optimized for stability and memory management

set -e  # Exit on any error

echo "🚀 Starting Stable Apps Document Vectorizer Deployment"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root (should not be)
if [ "$EUID" -eq 0 ]; then
    print_error "Do not run this script as root!"
    exit 1
fi

# Check if .env.stable exists
if [ ! -f ".env.stable" ]; then
    print_error ".env.stable file not found!"
    print_status "Please copy and configure .env.stable from the template"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running or not accessible"
    exit 1
fi

# Stop existing Stable Apps container if running
print_status "Stopping existing Document Vectorizer container..."
docker-compose -f docker-compose.stable.yml down 2>/dev/null || true

# Create necessary directories on host
print_status "Creating persistent directories..."
sudo mkdir -p /var/lib/docker/volumes/stable-data
sudo mkdir -p /var/lib/docker/volumes/stable-logs  
sudo mkdir -p /var/lib/docker/volumes/stable-cache
sudo mkdir -p /var/lib/docker/volumes/stable-tracker

# Set proper permissions
print_status "Setting directory permissions..."
sudo chown -R 1000:1000 /var/lib/docker/volumes/stable-*

# Create config directory if it doesn't exist
print_status "Preparing configuration..."
mkdir -p config

# Set proper permissions for config directory
chmod 755 config

# Create runtime settings file if it doesn't exist
if [ ! -f "config/runtime_settings.json" ]; then
    print_status "Creating runtime settings file..."
    echo '{}' > config/runtime_settings.json
    chmod 644 config/runtime_settings.json
fi

# Check for required credential files
if [ ! -f "config/client_secrets.json" ]; then
    print_warning "config/client_secrets.json not found"
    print_status "Please place your Google OAuth client secrets file at config/client_secrets.json"
fi

# Build the Docker image
print_status "Building Docker image..."
docker build -t document-vectorizer:latest .

# Check if build succeeded
if [ $? -ne 0 ]; then
    print_error "Docker build failed!"
    exit 1
fi

print_success "Docker image built successfully"

# Start the Stable Apps container
print_status "Starting Stable Apps Document Vectorizer..."
docker-compose -f docker-compose.stable.yml up -d

# Check if container started successfully
sleep 5
if docker-compose -f docker-compose.stable.yml ps | grep -q "Up"; then
    print_success "Stable Apps Document Vectorizer started successfully!"
    print_status "Dashboard available at: http://your-server-ip:8001"
    print_status "Container name: document-vectorizer-stable"
else
    print_error "Container failed to start!"
    print_status "Checking logs..."
    docker-compose -f docker-compose.stable.yml logs --tail=20
    exit 1
fi

# Show container status
print_status "Container Status:"
docker-compose -f docker-compose.stable.yml ps

# Show resource usage
print_status "Resource Usage:"
docker stats --no-stream document-vectorizer-stable 2>/dev/null || true

# Configuration reminder
print_warning "IMPORTANT: Before the app can work, you need to:"
echo "1. Configure .env.stable with your actual credentials"
echo "2. Place Google OAuth client secrets at config/client_secrets.json"  
echo "3. Generate OAuth token using: python convert_token_to_pickle.py /path/to/your/token.json"
echo "4. Verify Supabase credentials and database setup"

print_success "Deployment completed!"
print_status "Monitor logs with: docker-compose -f docker-compose.stable.yml logs -f"
print_status "Stop container with: docker-compose -f docker-compose.stable.yml down"