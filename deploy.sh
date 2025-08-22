#!/bin/bash

# Document Vectorizer Deployment Script
# Usage: ./deploy.sh [production|staging|local]

set -e

ENVIRONMENT=${1:-local}
COMPOSE_FILE=""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Document Vectorizer Deployment Script${NC}"
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."

if ! command_exists docker; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Set compose command (docker-compose vs docker compose)
if command_exists docker-compose; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

# Select compose file based on environment
case $ENVIRONMENT in
    production)
        COMPOSE_FILE="docker-compose.production.yml"
        ENV_FILE=".env"
        
        # Check for production requirements
        if [ ! -f "$ENV_FILE" ]; then
            echo -e "${YELLOW}Warning: .env file not found${NC}"
            echo "Creating from template..."
            cp .env.production .env
            echo -e "${RED}Please edit .env with your production values${NC}"
            exit 1
        fi
        
        if [ ! -f "credentials/google-credentials.json" ]; then
            echo -e "${RED}Error: Google credentials not found at credentials/google-credentials.json${NC}"
            exit 1
        fi
        ;;
        
    staging)
        COMPOSE_FILE="docker-compose.yml"
        ENV_FILE=".env.staging"
        ;;
        
    local)
        COMPOSE_FILE="docker-compose.yml"
        ENV_FILE=".env"
        ;;
        
    *)
        echo -e "${RED}Invalid environment: $ENVIRONMENT${NC}"
        echo "Usage: $0 [production|staging|local]"
        exit 1
        ;;
esac

# Build and deploy
echo -e "${GREEN}Building Docker image...${NC}"
$COMPOSE_CMD -f $COMPOSE_FILE build

echo -e "${GREEN}Stopping existing containers...${NC}"
$COMPOSE_CMD -f $COMPOSE_FILE down

echo -e "${GREEN}Starting application...${NC}"
$COMPOSE_CMD -f $COMPOSE_FILE up -d

# Wait for health check
echo -e "${YELLOW}Waiting for application to be healthy...${NC}"
sleep 5

# Check health
if curl -f http://localhost:5555/api/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Application is healthy${NC}"
    echo ""
    echo -e "${GREEN}Deployment successful!${NC}"
    echo -e "Dashboard available at: ${GREEN}http://localhost:5555${NC}"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    $COMPOSE_CMD -f $COMPOSE_FILE logs -f"
    echo "  Stop:         $COMPOSE_CMD -f $COMPOSE_FILE down"
    echo "  Restart:      $COMPOSE_CMD -f $COMPOSE_FILE restart"
    echo "  Check status: $COMPOSE_CMD -f $COMPOSE_FILE ps"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "Checking logs..."
    $COMPOSE_CMD -f $COMPOSE_FILE logs --tail=50
    exit 1
fi