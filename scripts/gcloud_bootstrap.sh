#!/usr/bin/env bash
# Mercury — one-shot bootstrap for the abm-isu GCP project.
#
# Run interactively the first time (the gcloud-auth steps need a browser).
# Re-running is safe; gcloud APIs that are already enabled return quickly.
#
# Prereq: `gcloud` CLI installed and on PATH.

set -euo pipefail

PROJECT="abm-isu"
REGION="us-central1"

echo "==> selecting project $PROJECT"
gcloud config set project "$PROJECT"
gcloud config set compute/region "$REGION"

echo "==> setting up Application Default Credentials (browser flow)"
echo "    Skip this if ADC already exists at"
echo "    %APPDATA%/gcloud/application_default_credentials.json"
read -p "    Run 'gcloud auth application-default login' now? [y/N] " yn
case "$yn" in
    [Yy]*)
        gcloud auth application-default login
        gcloud auth application-default set-quota-project "$PROJECT"
        ;;
    *)
        echo "    Skipping ADC step. Mercury will fail Vertex calls until ADC is set."
        ;;
esac

echo "==> enabling APIs (may take 1-2 min on first run)"
APIS=(
    aiplatform.googleapis.com
    generativelanguage.googleapis.com
    routes.googleapis.com
    places-backend.googleapis.com
    places.googleapis.com
    geocoding-backend.googleapis.com
    gmail.googleapis.com
    calendar-json.googleapis.com
    drive.googleapis.com
    sheets.googleapis.com
    docs.googleapis.com
    youtube.googleapis.com
    translate.googleapis.com
    vision.googleapis.com
    speech.googleapis.com
    texttospeech.googleapis.com
    books.googleapis.com
    kgsearch.googleapis.com
    admin.googleapis.com
    chat.googleapis.com
    meet.googleapis.com
)
for api in "${APIS[@]}"; do
    echo "    enabling $api"
    gcloud services enable "$api" --project="$PROJECT" 2>&1 | sed 's/^/      /'
done

echo "==> creating budget alert at \$5/month with 75% + 90% triggers"
BILLING_ACCOUNT=$(gcloud billing projects describe "$PROJECT" --format="value(billingAccountName)" | awk -F/ '{print $NF}')
if [ -n "$BILLING_ACCOUNT" ]; then
    gcloud billing budgets create \
        --billing-account="$BILLING_ACCOUNT" \
        --display-name="Mercury hard cap" \
        --budget-amount=5USD \
        --threshold-rule=percent=0.50 \
        --threshold-rule=percent=0.75 \
        --threshold-rule=percent=0.90 \
        --threshold-rule=percent=1.00 \
        --filter-projects="projects/$(gcloud projects describe $PROJECT --format='value(projectNumber)')" \
        2>&1 | sed 's/^/    /'
else
    echo "    No billing account linked to $PROJECT yet. Skipping budget."
    echo "    Link one at console.cloud.google.com/billing then re-run this script."
fi

echo "==> writing env hints to ~/.hermes/.env (idempotent)"
ENV_FILE="$HOME/.hermes/.env"
mkdir -p "$(dirname "$ENV_FILE")"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE" 2>/dev/null || true
upsert() {
    local key=$1 val=$2
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE" && rm "$ENV_FILE.bak" 2>/dev/null
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}
upsert GOOGLE_CLOUD_PROJECT "$PROJECT"
upsert GOOGLE_CLOUD_LOCATION "$REGION"
upsert GOOGLE_GENAI_USE_VERTEXAI "true"

echo
echo "==> done."
echo "    Verify with: mercury -z 'use google_search to tell me what time it is'"
echo "    Mercury's tool layer will route through Vertex + ADC, no API key required."
