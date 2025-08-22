#!/bin/bash

echo "========================================="
echo "Document Vectorizer - Docker Setup"
echo "========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://www.docker.com/get-started"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p config logs

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file with your credentials:"
    echo "   - SUPABASE_URL"
    echo "   - SUPABASE_KEY" 
    echo "   - OPENAI_API_KEY"
    echo "   - GOOGLE_DRIVE_FOLDER_ID (if different)"
    echo ""
    echo "Would you like to edit .env now? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    fi
fi

# Check for Google credentials
echo ""
echo "🔐 Checking Google Drive authentication..."
if [ ! -f config/google_credentials.json ] && [ ! -f config/token.json ]; then
    echo ""
    echo "⚠️  No Google Drive credentials found. You have two options:"
    echo ""
    echo "Option 1: Service Account (Recommended for Docker)"
    echo "  1. Go to https://console.cloud.google.com"
    echo "  2. Create service account with Drive API access"
    echo "  3. Download JSON key and save as: config/google_credentials.json"
    echo ""
    echo "Option 2: OAuth2 Token"
    echo "  1. First run locally: python main.py --mode setup-oauth"
    echo "  2. This will create config/token.json"
    echo ""
    echo "Press Enter when credentials are ready..."
    read
fi

# Build Docker image
echo ""
echo "🔨 Building Docker image..."
docker-compose build

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Docker setup complete!"
    echo ""
    echo "========================================="
    echo "Available Commands:"
    echo "========================================="
    echo ""
    echo "▶️  Start the service:"
    echo "   docker-compose up -d"
    echo ""
    echo "📋 View logs:"
    echo "   docker-compose logs -f"
    echo ""
    echo "🔄 Restart service:"
    echo "   docker-compose restart"
    echo ""
    echo "⏹  Stop service:"
    echo "   docker-compose down"
    echo ""
    echo "📊 Check status:"
    echo "   docker-compose ps"
    echo ""
else
    echo ""
    echo "❌ Docker build failed. Please check the error messages above."
    exit 1
fi