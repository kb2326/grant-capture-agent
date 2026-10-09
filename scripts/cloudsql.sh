set -euo pipefail
PROJECT=grant-capture-agent; INSTANCE=grant-capture-pg; REGION=us-central1
case "${1:-status}" in
  up)     gcloud sql instances patch "$INSTANCE" --project "$PROJECT" --activation-policy ALWAYS --quiet ;;
  down)   gcloud sql instances patch "$INSTANCE" --project "$PROJECT" --activation-policy NEVER --quiet ;;
  status) gcloud sql instances describe "$INSTANCE" --project "$PROJECT" --format "value(state,settings.activationPolicy)" ;;
  proxy)  cloud-sql-proxy "$PROJECT:$REGION:$INSTANCE" --port 5434 ;;
  *) echo "usage: $0 up|down|status|proxy"; exit 2 ;;
esac
