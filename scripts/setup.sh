#!/bin/bash

echo "Setting up Document Vectorizer..."

# Create necessary directories
mkdir -p config logs

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment template if not exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env with your credentials"
fi

# Make main script executable
chmod +x main.py

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your credentials"
echo "2. Set up Google Drive authentication:"
echo "   - For OAuth: python main.py --mode setup-oauth"
echo "   - For Service Account: place credentials in config/google_credentials.json"
echo "3. Run: python main.py"