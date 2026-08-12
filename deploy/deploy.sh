#!/usr/bin/env bash
# Deploy Reputation Sentinel Ops to the team's GCP hackathon sandbox project.
# tasks.md T051 (Cloud Run deploy) + T052 (enable IAP, allow-list managers).
#
# Run manually, step by step — do NOT pipe this whole file into `bash` blindly, review each
# gcloud command against your actual project/region first.
set -euo pipefail

: "${GCP_PROJECT:?Set GCP_PROJECT to your team's sandbox project id}"
: "${GCP_REGION:=asia-southeast2}"
SERVICE_NAME="reputation-sentinel-ops"
SCHEDULER_JOB_NAME="reputation-sentinel-ingestion"
SCHEDULER_FUNCTION_NAME="reputation-sentinel-scheduled-ingestion"

echo "== 1. Build & push the Streamlit+ADK container (T051) =="
gcloud builds submit --project "$GCP_PROJECT" --tag "gcr.io/$GCP_PROJECT/$SERVICE_NAME"

echo "== 2. Deploy to Cloud Run (T051) =="
gcloud run deploy "$SERVICE_NAME" \
  --project "$GCP_PROJECT" \
  --region "$GCP_REGION" \
  --image "gcr.io/$GCP_PROJECT/$SERVICE_NAME" \
  --set-env-vars "GCP_PROJECT=$GCP_PROJECT,GCP_REGION=$GCP_REGION,USE_SEED_DATA=true" \
  --no-allow-unauthenticated \
  --min-instances=0 --max-instances=2

echo "== 3. Deploy the scheduled-ingestion function (closes C2, research.md § Ingestion Scheduling) =="
gcloud functions deploy "$SCHEDULER_FUNCTION_NAME" \
  --project "$GCP_PROJECT" \
  --region "$GCP_REGION" \
  --gen2 \
  --runtime=python311 \
  --source=. \
  --entry-point=main \
  --trigger-http \
  --no-allow-unauthenticated \
  --set-env-vars "GCP_PROJECT=$GCP_PROJECT,GCP_REGION=$GCP_REGION" \
  --memory=512Mi

echo "== 4. Create the Cloud Scheduler job (every 15 min, SC-001) =="
FUNCTION_URL=$(gcloud functions describe "$SCHEDULER_FUNCTION_NAME" \
  --project "$GCP_PROJECT" --region "$GCP_REGION" --gen2 --format='value(serviceConfig.uri)')

gcloud scheduler jobs create http "$SCHEDULER_JOB_NAME" \
  --project "$GCP_PROJECT" \
  --location "$GCP_REGION" \
  --schedule "*/15 * * * *" \
  --uri "$FUNCTION_URL" \
  --http-method POST \
  --oidc-service-account-email "scheduler-invoker@${GCP_PROJECT}.iam.gserviceaccount.com"

echo "== 5. Restrict access to authorized managers (T052, closes C3) =="
echo "Deployed with --no-allow-unauthenticated above, which already blocks 100% of"
echo "unauthenticated access at Cloud Run's front door (Option B — see research.md §"
echo "Deployment Update for why full IAP was deferred). For EACH manager, grant invoker:"
echo "  gcloud run services add-iam-policy-binding $SERVICE_NAME \\"
echo "    --project=$GCP_PROJECT --region=$GCP_REGION \\"
echo "    --member='user:MANAGER_EMAIL_HERE' --role='roles/run.invoker'"
echo "Managers then access the app via:"
echo "  gcloud run services proxy $SERVICE_NAME --project=$GCP_PROJECT --region=$GCP_REGION"
echo ""
echo "(Optional, full production hardening) Upgrade to Identity-Aware Proxy for browser-"
echo "native SSO — needs an External HTTPS Load Balancer + managed SSL cert in front of"
echo "Cloud Run: https://cloud.google.com/iap/docs/enabling-cloud-run . Then:"
echo "  gcloud iap web add-iam-policy-binding --project=$GCP_PROJECT \\"
echo "    --member='user:MANAGER_EMAIL_HERE' --role='roles/iap.httpsResourceAccessor'"
echo ""
echo "== 6. Register each connected manager in Firestore =="
echo "The 'managers' collection needs a doc per manager with google_identity_email set to"
echo "the SAME email granted run.invoker above (src/models/manager.py), so"
echo "src/integrations/auth.py can resolve the authenticated identity to a Manager record."
