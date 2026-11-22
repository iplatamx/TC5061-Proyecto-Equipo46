#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=/opt/tc5061/semana-10
report_dir="$repo_root/reports/semana10"
bucket_file=/opt/tc5061/aws-artifact-bucket

if [[ ! -f "$bucket_file" ]]; then
  echo "No encuentro el nombre del bucket de artefactos: $bucket_file" >&2
  exit 1
fi
bucket=$(cat "$bucket_file")
cd "$repo_root"
mkdir -p "$report_dir"
rm -f "$report_dir/locust_report.html" "$report_dir"/locust_stats_*.csv "$report_dir/docker_stats_aws.csv"
printf 'timestamp_utc,service,cpu_percent,memory_usage\n' > "$report_dir/docker_stats_aws.csv"

docker compose --profile loadtest run --rm locust > /tmp/week10-locust.log 2>&1 &
locust_pid=$!
while kill -0 "$locust_pid" 2>/dev/null; do
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  for service in api mlflow; do
    container_id=$(docker compose ps -q "$service")
    if [[ -n "$container_id" ]]; then
      stats=$(docker stats --no-stream --format '{{.CPUPerc}},{{.MemUsage}}' "$container_id" 2>/dev/null || true)
      if [[ -n "$stats" ]]; then
        printf '%s,%s,%s\n' "$timestamp" "$service" "$stats" >> "$report_dir/docker_stats_aws.csv"
      fi
    fi
  done
  sleep 2
done

locust_status=0
wait "$locust_pid" || locust_status=$?
cp /tmp/week10-locust.log "$report_dir/locust_run.log"
aws s3 cp "$report_dir/" "s3://$bucket/reports/semana10/" --recursive
cat /tmp/week10-locust.log
exit "$locust_status"
