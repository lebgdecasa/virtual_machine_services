# Google Cloud Run Deployment Guide

This guide will help you deploy your FastAPI application to Google Cloud Run with proper secret management.

## Prerequisites

1. **Google Cloud CLI**: Install and authenticate
   ```bash
   # Install gcloud CLI (if not already installed)
   # https://cloud.google.com/sdk/docs/install

   # Authenticate
   gcloud auth login

   # Set your project
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Enable Required APIs**:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   gcloud services enable cloudbuild.googleapis.com
   ```

## Quick Setup

### Option 1: Automated Setup (Recommended)

Run the provided setup script:

```bash
./setup-gcp-secrets.sh
```

This script will:
- Create all required secrets
- Set up proper IAM permissions
- Generate deployment commands
- Create a service account

### Option 2: Manual Setup

#### 1. Create Secrets

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create secrets
echo -n "your-gemini-api-key" | gcloud secrets create NEXT_PUBLIC_GEMINI_API_KEY --data-file=-
echo -n "your-supabase-url" | gcloud secrets create NEXT_PUBLIC_SUPABASE_URL --data-file=-
echo -n "your-supabase-service-key" | gcloud secrets create SUPABASE_SERVICE_ROLE_KEY --data-file=-
echo -n "your-zoho-password" | gcloud secrets create ZOHO_PASSWORD --data-file=-
```

#### 2. Grant Access to Secrets

```bash
# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding NEXT_PUBLIC_GEMINI_API_KEY \
  --member="serviceAccount:$PROJECT_ID-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding NEXT_PUBLIC_SUPABASE_URL \
  --member="serviceAccount:$PROJECT_ID-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding SUPABASE_SERVICE_ROLE_KEY \
  --member="serviceAccount:$PROJECT_ID-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding ZOHO_PASSWORD \
  --member="serviceAccount:$PROJECT_ID-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Deployment

### Deploy to Cloud Run

```bash
gcloud run deploy nextraction-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account=$PROJECT_ID-compute@developer.gserviceaccount.com \
  --set-env-vars="NEXT_PUBLIC_GEMINI_API_KEY=$(gcloud secrets versions access latest --secret=NEXT_PUBLIC_GEMINI_API_KEY)" \
  --set-env-vars="NEXT_PUBLIC_SUPABASE_URL=$(gcloud secrets versions access latest --secret=NEXT_PUBLIC_SUPABASE_URL)" \
  --set-env-vars="SUPABASE_SERVICE_ROLE_KEY=$(gcloud secrets versions access latest --secret=SUPABASE_SERVICE_ROLE_KEY)" \
  --set-env-vars="ZOHO_PASSWORD=$(gcloud secrets versions access latest --secret=ZOHO_PASSWORD)"
```

### Alternative: Using Secret Manager Integration

For better security, you can use Cloud Run's native secret integration:

```bash
gcloud run deploy nextraction-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account=$PROJECT_ID-compute@developer.gserviceaccount.com \
  --set-secrets="NEXT_PUBLIC_GEMINI_API_KEY=NEXT_PUBLIC_GEMINI_API_KEY:latest" \
  --set-secrets="NEXT_PUBLIC_SUPABASE_URL=NEXT_PUBLIC_SUPABASE_URL:latest" \
  --set-secrets="SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest" \
  --set-secrets="ZOHO_PASSWORD=ZOHO_PASSWORD:latest"
```

## Environment Variables

Your application uses the following environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_GEMINI_API_KEY` | Google Gemini API key for LLM operations | Yes |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key for database access | Yes |
| `ZOHO_PASSWORD` | Zoho email password for sending emails | Yes |

## Local Development

1. Copy the environment template:
   ```bash
   cp env.template .env
   ```

2. Fill in your actual values in `.env`

3. Run locally:
   ```bash
   pip install -r requirements.txt
   uvicorn main.api:app --reload --host 0.0.0.0 --port 8000
   ```

## Monitoring and Logs

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=nextraction-backend" --limit 50
```

### Monitor in Console
- Go to [Google Cloud Console](https://console.cloud.google.com)
- Navigate to Cloud Run
- Select your service
- View metrics, logs, and configuration

## Security Best Practices

1. **Use Service Accounts**: Always use dedicated service accounts for Cloud Run
2. **Least Privilege**: Only grant necessary permissions
3. **Secret Rotation**: Regularly rotate your API keys and secrets
4. **Environment Separation**: Use different projects/regions for dev/staging/prod
5. **Network Security**: Consider using VPC connectors for private resources

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure the service account has access to secrets
2. **Secret Not Found**: Verify secret names and project ID
3. **Build Failures**: Check Dockerfile and requirements.txt
4. **Runtime Errors**: Check logs for missing environment variables

### Debug Commands

```bash
# Check service account permissions
gcloud projects get-iam-policy $PROJECT_ID

# List secrets
gcloud secrets list

# Test secret access
gcloud secrets versions access latest --secret=NEXT_PUBLIC_GEMINI_API_KEY

# View service details
gcloud run services describe nextraction-backend --region=us-central1
```

## Cost Optimization

1. **Set Resource Limits**: Configure CPU and memory limits
2. **Use Minimum Instances**: Set to 0 for cost savings (with cold start trade-off)
3. **Request Timeout**: Set appropriate timeouts
4. **Concurrency**: Adjust based on your workload

```bash
gcloud run deploy nextraction-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=300
```

## Next Steps

1. Set up CI/CD pipeline with GitHub Actions or Cloud Build
2. Configure custom domain and SSL
3. Set up monitoring and alerting
4. Implement health checks and readiness probes
5. Consider using Cloud SQL for persistent data storage
