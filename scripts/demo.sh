#!/usr/bin/env bash
#
# 운영 자동화 신고 triage MVP 한 번에 도는 스모크 데모.
#
# 전제: `docker compose up -d --build --wait` 가 끝나 있어야 한다.
# 검증 흐름:
#   1) /health 200
#   2) samples/{fraud,spam,abuse}.json 으로 POST /reports 3건
#   3) workflow가 끝날 시간을 잠깐 주고 GET /reports/{id} 로 분류 결과 확인
#   4) 큐별 GET /queues/{queue}/reports 으로 라우팅 결과 확인
#   5) GET /metrics/events 로 후속 소비자 카운터 증가 확인
#
# 환경변수:
#   API   기본 http://localhost:8000
#   WAIT  분류 완료 대기 초 (기본 2)
#   JQ    jq 경로 (기본 jq). 없으면 raw 출력 fallback.

set -euo pipefail

API="${API:-http://localhost:8000}"
WAIT="${WAIT:-2}"
JQ="${JQ:-jq}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SAMPLES="$ROOT/samples"

if ! command -v "$JQ" >/dev/null 2>&1; then
  # jq 없으면 그냥 cat — 데모는 계속 돈다.
  JQ="cat"
fi

step() { printf '\n\033[1;34m== %s ==\033[0m\n' "$*"; }

step "1) health"
curl -fsS "$API/health" | "$JQ"

step "2) POST 3 samples"
declare -a IDS=()
for kind in fraud spam abuse; do
  resp="$(curl -fsS -X POST "$API/reports" \
            -H 'content-type: application/json' \
            --data-binary "@$SAMPLES/$kind.json")"
  rid="$(printf '%s' "$resp" | "$JQ" -r '.report_id')"
  IDS+=("$rid")
  printf '  %-6s -> %s\n' "$kind" "$rid"
done

step "3) workflow 완료 대기 ${WAIT}s"
sleep "$WAIT"

step "4) GET /reports/{id} (분류 결과)"
for rid in "${IDS[@]}"; do
  curl -fsS "$API/reports/$rid" \
    | "$JQ" '{report_id:.id, status, category:.classification.category, priority:.classification.priority, queue:.classification.routed_queue}'
done

step "5) GET /queues/{queue}/reports (큐별 라우팅 확인)"
for q in fraud-review spam-review abuse-review; do
  printf '  %s\n' "$q"
  curl -fsS "$API/queues/$q/reports?limit=3" \
    | "$JQ" '{queue:.queue_name, count:(.items|length), top:[.items[]|{report_id, category, priority}]}'
done

step "6) GET /metrics/events (후속 소비자 카운터)"
curl -fsS "$API/metrics/events" | "$JQ"

printf '\n\033[1;32m✓ demo complete\033[0m\n'
