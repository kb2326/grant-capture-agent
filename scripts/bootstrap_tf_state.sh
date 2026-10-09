set -euo pipefail
PROJECT=grant-capture-agent
BUCKET=gs://${PROJECT}-tfstate
gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1 || \
  gcloud storage buckets create "$BUCKET" --project "$PROJECT" --location us-central1 \
    --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update "$BUCKET" --versioning
echo "state bucket ready: $BUCKET"
