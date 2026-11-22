#!/usr/bin/env bash
set -Eeuo pipefail

base=/opt/tc5061
repo="$base/semana-10"
commit="${1:?Usage: deploy_on_instance.sh <40-character-commit-sha>}"
if [[ ! "$commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid commit SHA: $commit" >&2
  exit 2
fi

docker load --input /tmp/week10-api-image.tar
printf '%s\n' \
  "MIBICI_API_IMAGE=mibici-equipo46-api:$commit" \
  "MIBICI_LEGACY_MODELS_DIR=$base/semana-07/mlruns/2/models" \
  > "$repo/.env"
chown ec2-user:ec2-user "$repo/.env"
cd "$repo"
docker compose up -d --no-build

healthy=false
for attempt in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null \
    && curl --fail --silent http://127.0.0.1:5000/health >/dev/null; then
    healthy=true
    break
  fi
  sleep 5
done

if [[ "$healthy" != true ]]; then
  docker compose ps
  docker compose logs --tail=100 api mlflow
  exit 1
fi

docker compose ps
echo "Deployment $commit is healthy."