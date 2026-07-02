#!/usr/bin/env bash
set -e

# Colors for terminal styling
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}        ORKESTER GCP DEPLOYMENT SCRIPT         ${NC}"
echo -e "${BLUE}===============================================${NC}"

# Check for gcloud CLI
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Ensure user is authenticated
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status=ACTIVE --format="value(account)" 2>/dev/null)
if [ -z "$ACTIVE_ACCOUNT" ]; then
    echo -e "${YELLOW}No active GCP account found. Starting gcloud login...${NC}"
    gcloud auth login
    ACTIVE_ACCOUNT=$(gcloud auth list --filter=status=ACTIVE --format="value(account)" 2>/dev/null)
fi
echo -e "${GREEN}Authenticated as: $ACTIVE_ACCOUNT${NC}"

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    echo -e "${YELLOW}No default GCP project set.${NC}"
    read -p "Enter your GCP Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
else
    read -p "Use current project '$PROJECT_ID'? [Y/n]: " use_current
    use_current=${use_current:-Y}
    if [[ "$use_current" =~ ^[Nn] ]]; then
        read -p "Enter your GCP Project ID: " PROJECT_ID
        gcloud config set project "$PROJECT_ID"
    fi
fi

# Confirm project ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: Project ID is required.${NC}"
    exit 1
fi

# Ask for Region
read -p "Enter GCP Region [us-central1]: " REGION
REGION=${REGION:-us-central1}

echo -e "${BLUE}Enabling Google Cloud APIs...${NC}"
gcloud services enable \
    artifactregistry.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com

# Create Artifact Registry repo if it doesn't exist
REPO_NAME="orkester-repo"
echo -e "${BLUE}Checking if Artifact Registry repository '$REPO_NAME' exists in $REGION...${NC}"
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" &>/dev/null; then
    echo -e "${BLUE}Creating Artifact Registry repository '$REPO_NAME' in $REGION...${NC}"
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Orkester Container Repository" \
        --quiet
else
    echo -e "${GREEN}Repository '$REPO_NAME' already exists.${NC}"
fi

# Read API keys from .env if present
ENV_FILE=".env"
GROQ_API_KEY=""
GEMINI_API_KEY=""
MISTRAL_API_KEY=""

if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}Found local .env file. Extracting API keys...${NC}"
    # Read variables from .env file
    GROQ_API_KEY=$(grep -E "^GROQ_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '\r\n')
    GEMINI_API_KEY=$(grep -E "^GEMINI_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '\r\n')
    MISTRAL_API_KEY=$(grep -E "^MISTRAL_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '\r\n')
fi

# Prompt for API keys if they are not set
if [ -z "$GROQ_API_KEY" ]; then
    read -p "Enter GROQ_API_KEY: " GROQ_API_KEY
fi
if [ -z "$GEMINI_API_KEY" ]; then
    read -p "Enter GEMINI_API_KEY: " GEMINI_API_KEY
fi
if [ -z "$MISTRAL_API_KEY" ]; then
    read -p "Enter MISTRAL_API_KEY: " MISTRAL_API_KEY
fi

# ----------------- BACKEND DEPLOYMENT -----------------
echo -e "${BLUE}-----------------------------------------------${NC}"
echo -e "${BLUE}1. Building and deploying Backend...${NC}"
echo -e "${BLUE}-----------------------------------------------${NC}"

BACKEND_IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/backend:latest"

# Build using Cloud Build
echo -e "${BLUE}Submitting Backend build to Cloud Build...${NC}"
gcloud builds submit --tag "$BACKEND_IMAGE" .

# Deploy to Cloud Run
echo -e "${BLUE}Deploying Backend service to Cloud Run...${NC}"
gcloud run deploy orkester-backend \
    --image "$BACKEND_IMAGE" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --port 8000 \
    --set-env-vars "GROQ_API_KEY=$GROQ_API_KEY,GEMINI_API_KEY=$GEMINI_API_KEY,MISTRAL_API_KEY=$MISTRAL_API_KEY"

# Get backend URL
BACKEND_URL=$(gcloud run services describe orkester-backend --platform managed --region "$REGION" --format="value(status.url)")
echo -e "${GREEN}Backend successfully deployed at: $BACKEND_URL${NC}"

# ----------------- FRONTEND DEPLOYMENT -----------------
echo -e "${BLUE}-----------------------------------------------${NC}"
echo -e "${BLUE}2. Building and deploying Frontend...${NC}"
echo -e "${BLUE}-----------------------------------------------${NC}"

FRONTEND_IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/frontend:latest"

# Build using Cloud Build
echo -e "${BLUE}Submitting Frontend build to Cloud Build...${NC}"
gcloud builds submit --tag "$FRONTEND_IMAGE" ./frontend

# Deploy to Cloud Run
echo -e "${BLUE}Deploying Frontend service to Cloud Run...${NC}"
gcloud run deploy orkester-frontend \
    --image "$FRONTEND_IMAGE" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --set-env-vars "BACKEND_URL=$BACKEND_URL"

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe orkester-frontend --platform managed --region "$REGION" --format="value(status.url)")

echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}        DEPLOYMENT COMPLETED SUCCESSFULLY!      ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}Frontend URL: ${FRONTEND_URL}${NC}"
echo -e "${GREEN}Backend URL:  ${BACKEND_URL}${NC}"
echo -e "${BLUE}===============================================${NC}"
