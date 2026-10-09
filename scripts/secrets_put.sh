set -euo pipefail
PROJECT=grant-capture-agent
set -a; source .env; set +a
put() { printf '%s' "$2" | gcloud secrets versions add "$1" --project "$PROJECT" --data-file=- >/dev/null && echo "updated $1"; }
[ -n "${SIMPLER_GRANTS_API_KEY:-}" ] && put simpler-grants-api-key "$SIMPLER_GRANTS_API_KEY"
[ -n "${SAM_API_KEY:-}" ] && put sam-api-key "$SAM_API_KEY"
