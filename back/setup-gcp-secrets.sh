#!/bin/bash

# Google Cloud Secrets Setup Script
# This script creates and configures secrets for your FastAPI application

set -e  # Exit on any error

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

# Check if gcloud is installed and authenticated
check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_error "No active gcloud authentication found. Please run 'gcloud auth login'"
        exit 1
    fi
}

# Get current project ID
get_project_id() {
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        print_error "No project ID found. Please set it with 'gcloud config set project YOUR_PROJECT_ID'"
        exit 1
    fi
    print_status "Using project: $PROJECT_ID"
}

# Enable required APIs
enable_apis() {
    print_status "Enabling required Google Cloud APIs..."
    gcloud services enable secretmanager.googleapis.com
    gcloud services enable run.googleapis.com
    print_success "APIs enabled successfully"
}

# Create secrets
create_secrets() {
    print_status "Creating secrets..."

    # Check if secrets already exist
    if gcloud secrets describe NEXT_PUBLIC_GEMINI_API_KEY &>/dev/null; then
        print_warning "Secret NEXT_PUBLIC_GEMINI_API_KEY already exists. Skipping creation."
    else
        echo -n "Enter your Gemini API key: "
        read GEMINI_KEY
        echo
        echo -n "$GEMINI_KEY" | gcloud secrets create NEXT_PUBLIC_GEMINI_API_KEY --data-file=-
        print_success "Created NEXT_PUBLIC_GEMINI_API_KEY secret"
    fi

    if gcloud secrets describe NEXT_PUBLIC_SUPABASE_URL &>/dev/null; then
        print_warning "Secret NEXT_PUBLIC_SUPABASE_URL already exists. Skipping creation."
    else
        echo -n "Enter your Supabase URL: "
        read SUPABASE_URL
        echo -n "$SUPABASE_URL" | gcloud secrets create NEXT_PUBLIC_SUPABASE_URL --data-file=-
        print_success "Created NEXT_PUBLIC_SUPABASE_URL secret"
    fi

    if gcloud secrets describe SUPABASE_SERVICE_ROLE_KEY &>/dev/null; then
        print_warning "Secret SUPABASE_SERVICE_ROLE_KEY already exists. Skipping creation."
    else
        echo -n "Enter your Supabase service role key: "
        read SUPABASE_KEY
        echo
        echo -n "$SUPABASE_KEY" | gcloud secrets create SUPABASE_SERVICE_ROLE_KEY --data-file=-
        print_success "Created SUPABASE_SERVICE_ROLE_KEY secret"
    fi

    if gcloud secrets describe ZOHO_PASSWORD &>/dev/null; then
        print_warning "Secret ZOHO_PASSWORD already exists. Skipping creation."
    else
        echo -n "Enter your Zoho password: "
        read ZOHO_PASSWORD
        echo
        echo -n "$ZOHO_PASSWORD" | gcloud secrets create ZOHO_PASSWORD --data-file=-
        print_success "Created ZOHO_PASSWORD secret"
    fi
}

# Grant Cloud Run access to secrets
grant_secret_access() {
    print_status "Granting Cloud Run access to secrets..."

    # Get the default compute service account (use project number, not project name)
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

    # Grant access to each secret
    for secret in NEXT_PUBLIC_GEMINI_API_KEY NEXT_PUBLIC_SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY ZOHO_PASSWORD; do
        gcloud secrets add-iam-policy-binding "$secret" \
            --member="serviceAccount:${COMPUTE_SA}" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet
        print_success "Granted access to $secret"
    done
}

# Create a service account for Cloud Run (optional but recommended)
create_service_account() {
    print_status "Creating service account for Cloud Run..."

    SA_NAME="nextraction-cloud-run"
    SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

    if gcloud iam service-accounts describe "$SA_EMAIL" &>/dev/null; then
        print_warning "Service account $SA_EMAIL already exists. Skipping creation."
    else
        gcloud iam service-accounts create "$SA_NAME" \
            --display-name="Nextraction Cloud Run Service Account" \
            --description="Service account for Nextraction Cloud Run deployment"
        print_success "Created service account: $SA_EMAIL"
    fi

    # Grant the service account access to secrets
    for secret in NEXT_PUBLIC_GEMINI_API_KEY NEXT_PUBLIC_SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY ZOHO_PASSWORD; do
        gcloud secrets add-iam-policy-binding "$secret" \
            --member="serviceAccount:${SA_EMAIL}" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet
        print_success "Granted $SA_EMAIL access to $secret"
    done

    echo
    print_status "Service account created: $SA_EMAIL"
    print_warning "Make sure to use this service account when deploying to Cloud Run:"
    echo "gcloud run deploy --service-account=$SA_EMAIL"
}

# Generate deployment command
generate_deployment_command() {
    echo
    print_status "Deployment command for Cloud Run:"
    echo "================================================"

    # Get the project number for the service account
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

    cat << EOF
gcloud run deploy nextraction-backend \\
  --source . \\
  --platform managed \\
  --region us-central1 \\
  --allow-unauthenticated \\
  --service-account=${COMPUTE_SA} \\
  --set-env-vars="NEXT_PUBLIC_GEMINI_API_KEY=\$(gcloud secrets versions access latest --secret=NEXT_PUBLIC_GEMINI_API_KEY)" \\
  --set-env-vars="NEXT_PUBLIC_SUPABASE_URL=\$(gcloud secrets versions access latest --secret=NEXT_PUBLIC_SUPABASE_URL)" \\
  --set-env-vars="SUPABASE_SERVICE_ROLE_KEY=\$(gcloud secrets versions access latest --secret=SUPABASE_SERVICE_ROLE_KEY)" \\
  --set-env-vars="ZOHO_PASSWORD=\$(gcloud secrets versions access latest --secret=ZOHO_PASSWORD)"
EOF
    echo "================================================"
}

# Main execution
main() {
    echo "🚀 Setting up Google Cloud Secrets for Nextraction Backend"
    echo "=========================================================="

    check_gcloud
    get_project_id
    enable_apis
    create_secrets
    grant_secret_access
    create_service_account
    generate_deployment_command

    echo
    print_success "✅ Secrets setup completed successfully!"
    print_status "Next steps:"
    echo "1. Deploy your application using the command above"
    echo "2. Test your endpoints to ensure secrets are working"
    echo "3. Monitor your application in the Google Cloud Console"
}

# Run main function
main "$@"
