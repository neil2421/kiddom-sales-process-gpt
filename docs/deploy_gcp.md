# Deploying to Google Cloud Run

## Prerequisites
- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed locally (for testing)
- All GitHub secrets configured (see README)

## Manual Deployment

1. **Build the Docker image:**
   ```bash
   docker build -t kiddom-sales-gpt .
   ```

2. **Tag for GCR:**
   ```bash
   docker tag kiddom-sales-gpt gcr.io/YOUR_PROJECT_ID/kiddom-sales-gpt
   ```

3. **Push to GCR:**
   ```bash
   docker push gcr.io/YOUR_PROJECT_ID/kiddom-sales-gpt
   ```

4. **Deploy to Cloud Run:**
   ```bash
   gcloud run deploy kiddom-sales-gpt \
     --image gcr.io/YOUR_PROJECT_ID/kiddom-sales-gpt \
     --region us-central1 \
     --platform managed \
     --allow-unauthenticated \
     --set-env-vars "OPENAI_API_KEY=...,PINECONE_API_KEY=...,PINECONE_ENV=...,GOOGLE_CREDENTIALS=...,SFDC_USER=...,SFDC_PASS=...,SFDC_TOKEN=..."
   ```

## Automated Deployment (CI/CD)
Pushing to `main` triggers the GitHub Actions workflow at `.github/workflows/deploy.yml`, which builds, pushes, and deploys automatically.

## Verifying
```bash
curl https://YOUR_CLOUD_RUN_URL/health
```

Should return: `{"status": "ok"}`
