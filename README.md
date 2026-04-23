# Report Triage Agent

사용자 신고를 받아서 1차 분류하고 운영 큐로 자동 라우팅하는 운영 자동화 MVP.

- **FastAPI** — 신고 접수/조회 API 입구
- **Temporal** — 신고 분류부터 큐 배정까지 비동기 워크플로우
- **PostgreSQL** — 신고 원본·분류 결과·큐 아이템 저장
- **NATS JetStream** — 분류 완료/큐 라우팅 이벤트를 후속 시스템으로 전달

목표는 정확한 AI 모델이 아니라 **운영 가능한 신고 triage 흐름**을 작은 서비스로 설계·구현하는 것이다.

> 상세 기획·요구사항·워크플로우 설계: [`docs/`](./docs/README.md)

## 빠른 시작

전제: Docker Desktop이 실행 중이어야 한다.

```bash
docker compose up -d --build --wait
```

기동되는 컨테이너:

| 서비스 | 포트 | 역할 |
|---|---|---|
| `postgres` | `5432` | 앱 DB(`triage`) + Temporal DB(`temporal`, `temporal_visibility`) |
| `nats` | `4222`, `8222` | JetStream + 모니터링 HTTP |
| `temporal` | `7233` | Temporal 서버 (auto-setup) |
| `temporal-ui` | `8080` | Workflow 실행 트레이스 확인 |
| `api` | `8000` | FastAPI |
| `worker` | — | Temporal worker |
| `consumer` | — | JetStream 후속 소비자 (event_metrics 카운터 누적) |
| `frontend` | `3000` | 운영자 큐 브라우저 (Next.js 데모 화면) |

종료:

```bash
docker compose down       # DB 유지
docker compose down -v    # 초기화 (스키마 변경 후엔 이걸 써야 한다)
```

> **스키마 변경 시 주의.** Alembic을 의도적으로 생략했기 때문에(§설계 의사결정) `Base.metadata.create_all`은 *없는 테이블만* 만든다. 컬럼 추가/제약 변경은 반영되지 않으므로 모델을 바꿨다면 `docker compose down -v` 후 재기동해야 한다. 운영 단계에서는 마이그레이션 1개를 추가하는 게 첫 단계.

## 동작 검증

### 0. 단위·워크플로 테스트

```bash
docker compose exec api pytest
# 38 passed in ~4s (워크플로 테스트는 첫 실행 시 Temporal test-server 다운로드 ~5s)
```

구성:
- 순수 함수 27개 (classifier/routing/priority/review)
- 이벤트 핸들러 5개 (decode_subject 화이트리스트·malformed payload 처리)
- publisher dedup 배선 3개 (`Nats-Msg-Id` 헤더가 publish 시 정확히 들어가는지)
- 워크플로 3개: happy-path / publish 실패 후에도 mark_classified 도달(best-effort) / route 실패 시 mark_failed

워크플로 테스트는 `WorkflowEnvironment.start_time_skipping()`에 가짜 activity를 주입해 단계 순서·상태 전파·실패 경로 정책을 확인한다 (DB·NATS 미접근).

### 1. 헬스체크

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 2. 샘플 3건 — 서로 다른 큐로 라우팅 확인 (한 번에)

```bash
./scripts/demo.sh
# health → samples/{fraud,spam,abuse}.json POST → 분류 결과 → 큐별 라우팅 → 카운터
# 환경변수: API(기본 localhost:8000), WAIT(분류 대기 초, 기본 2)
```

스크립트가 도는 6단계는 §1·§3·§4·§8을 한 번에 묶은 것이다. 각 단계를 손으로
하나씩 보고 싶으면 아래 §3~§8을 그대로 따라가면 된다. 페이로드는
[`samples/{fraud,spam,abuse}.json`](./samples)에 있다.

### 3. 분류 결과 조회

```bash
curl -sS http://localhost:8000/reports/<report_id> | jq
# status=classified, classification.routed_queue=fraud-review …
```

### 4. 큐별 목록

```bash
curl -sS 'http://localhost:8000/queues/fraud-review/reports?limit=10' | jq
```

페이지네이션은 `(enqueued_at desc, id desc)` 복합 키셋이고 cursor는 `{ISO8601}|{queue_item_id}` 토큰이다.
ISO8601의 `+00:00`은 그대로 GET 파라미터에 박으면 공백으로 디코드되니 **percent-encode 필수**:

```bash
NEXT=$(curl -sS 'http://localhost:8000/queues/spam-review/reports?limit=2' \
  | jq -r '.next_cursor')
curl -sS --get 'http://localhost:8000/queues/spam-review/reports' \
  --data-urlencode "limit=2" --data-urlencode "cursor=$NEXT" | jq
```

잘못된 cursor는 `400 {"detail":"invalid cursor: ..."}`으로 응답한다.

### 5. 재처리

```bash
curl -sS -X POST http://localhost:8000/reports/<report_id>/reprocess
# status=queued, message=reprocess requested
```

### 6. 워크플로 실행 트레이스

브라우저에서 [http://localhost:8080](http://localhost:8080) → `default` namespace → `Workflows` 탭.

### 7. JetStream 이벤트 누적

```bash
curl -sS 'http://localhost:8222/jsz?streams=true' \
  | jq '.account_details[0].stream_detail[0].state | {messages, last_seq}'
# 신고 1건당 2개 이벤트(triaged, routed)가 쌓인다
```

### 8. JetStream 후속 소비자 카운터

```bash
curl -sS http://localhost:8000/metrics/events | jq
# {"items":[{"subject":"queue.routed","count":N,...},{"subject":"report.triaged","count":N,...}]}
```

신고 1건당 두 카운터가 각각 +1 된다. consumer 컨테이너의 durable subscription
두 개(`triage-metrics-triaged`, `triage-metrics-routed`)가 메시지를 ack하고
`event_metrics` 테이블에 누적한다. 즉 publish만 하지 않고 후속 소비자가
실제로 읽는다는 사실을 운영 화면 한 줄로 확인할 수 있다.

### 9. 운영자 큐 브라우저 (프론트)

브라우저에서 [http://localhost:3000](http://localhost:3000) → 4개 큐 탭(`fraud-review` / `spam-review` / `abuse-review` / `general-review`) 중 하나를 선택해 큐별 분류 결과를 표 형태로 확인.
얇은 데모용 Next.js 한 페이지이며, 내부적으로 `GET /queues/{queue}/reports`만 호출한다 (인증·필터·페이지네이션 UI 없음).

## API 요약

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET`  | `/health` | 헬스체크 |
| `POST` | `/reports` | 신고 생성 + workflow 시작 (202). `Idempotency-Key` 헤더 지원 |
| `GET`  | `/reports/{report_id}` | 신고 + 분류 결과 조회 |
| `POST` | `/reports/{report_id}/reprocess` | 재처리 시작 (202, 어떤 상태에서도 즉시 가능) |
| `GET`  | `/queues/{queue_name}/reports` | 큐별 신고 요약 목록 (커서 페이지네이션) |
| `GET`  | `/metrics/events` | JetStream 후속 소비자 카운터 |

**POST /reports 멱등성.** `Idempotency-Key` 헤더를 보내면 같은 키로 재요청해도 두 번째 요청은 새 row를 만들지 않고 기존 `report_id`를 그대로 돌려준다. 클라이언트가 응답 유실로 retry할 때 중복 신고가 안 만들어진다. 헤더가 없으면 매 요청 새 row(기존 동작 유지). 동시 요청 race는 DB unique 제약 + IntegrityError 재조회로 흡수한다.

```bash
KEY=$(uuidgen)
curl -sS -X POST http://localhost:8000/reports \
  -H "Idempotency-Key: $KEY" -H 'content-type: application/json' \
  --data-binary @samples/spam.json | jq .report_id
# 같은 KEY로 다시 보내도 동일 report_id 반환
```

상세 스펙: [`docs/04-api-spec.md`](./docs/04-api-spec.md)

## 설계 의사결정

- **FastAPI는 얇게.** 라우터는 입력 검증·DB 저장·workflow 시작만 담당한다. 장기 실행 흐름은 Temporal로 넘긴다.
- **장기 흐름은 Temporal workflow.** background task를 안 쓴 이유는 프로세스 재시작 후에도 추적 가능해야 하고(NFR-2), 단계별 retry/fallback이 필요하기 때문이다.
- **NATS JetStream은 "후속 시스템 경계".** 핵심 처리 엔진이 아니라 다운스트림 소비자가 FastAPI 호출 없이 결과를 받아갈 수 있게 하는 비동기 경계로 사용한다(NFR-3). 그 경계를 프로세스 경계로도 실체화하기 위해 후속 소비자(`consumer`)는 worker와 별도 컨테이너로 분리했고, durable subscription 두 개로 메시지를 받아 `event_metrics` 카운터에 누적한다.
- **`reports.status`가 단일 진실 원본.** API는 Temporal workflow execution 상태를 직접 참조하지 않는다. activity가 DB에 상태를 기록하고, API는 DB만 읽는다 (`docs/03-product-requirements.md` FR-2). workflow 시작 자체가 실패하면 status를 `workflow_start_failed`로 명시 — 운영자가 GET 한 번으로 "분류가 실패"인지 "workflow가 시작조차 못 했는지" 구분할 수 있게 한다.
- **NATS publish는 best-effort + publisher-side dedup.** classification·queue_item이 DB에 commit된 뒤의 `publish_triage_events_activity` 실패는 workflow에서 격리해서 잡고 그대로 `mark_classified`로 진행한다 (재시도는 `_DEFAULT_RETRY`로 3회 시도 후 포기). NATS는 "후속 시스템 경계"이지 핵심 처리 엔진이 아니라서, downstream 카운터가 비는 것보다 `reports.status`를 `failed`로 되돌려 "분류 자체가 실패"한 것처럼 보이는 게 운영자에게 더 큰 혼선이다. 다만 `publish_triaged → publish_queue_routed` 두 publish 중 한쪽이 실패해 워크플로 retry로 같은 메시지가 중복 발행되는 시나리오를 막기 위해 publisher가 `Nats-Msg-Id: {subject}:{report_id}` 헤더를 박고, JetStream stream에 `duplicate_window=120s`를 설정한다. 누락분은 `/metrics/events`로 관찰 가능하고, 운영성이 더 중요해지면 outbox 패턴으로 강화한다.
- **분류는 규칙 기반.** 정확도보다 운영 가능한 흐름을 우선한다. classifier 인터페이스는 `(reason_code, description, metadata) -> ClassificationResult` 한 줄짜리라 추후 LLM으로 교체 가능.
- **DB 스키마는 `create_all`로 생성.** MVP 속도를 위해 Alembic을 생략하고 앱 lifespan에서 테이블을 만든다. 운영성이 필요해지는 시점에 초기 migration 1개를 추가하면 된다 (`docs/05-data-model.md` §7.2).
- **재처리는 upsert-overwrite + active workflow ≤ 1.** classification·queue item은 `report_id` 기준으로 최신 1건만 유지하고 이력 테이블은 두지 않는다. workflow_id는 모든 run에 대해 `report-triage-{report_id}` 단일 ID를 사용하고, Temporal `WorkflowIDReusePolicy.TERMINATE_IF_RUNNING`으로 새 run 시작 시 기존 running run을 자동 종료시킨다. 결과는 새 run의 결과로 덮어써지고 stale run의 늦은 write는 cancellation으로 차단된다. API 게이트는 두지 않으며 어떤 상태에서도 운영자가 즉시 재분류할 수 있다 (`docs/06-workflow-and-events.md` §workflow_id 전략).

## 폴더 구조

```
backend/
  app/
    api/         # FastAPI 라우터
    core/        # 설정/ID 유틸
    db/          # SQLAlchemy 모델·세션
    schemas/     # Pydantic 스키마 (요청/응답/이벤트)
    services/    # 분류·우선순위·라우팅 순수 로직 + repo
    messaging/   # NATS JetStream publish + 후속 소비자(consumer.py) 엔트리포인트
    temporal/    # workflow / activity / client / worker
    main.py      # FastAPI 앱 + lifespan
  Dockerfile
  scripts/init-db.sh  # postgres 초기화 시 temporal DB 생성
frontend/        # Next.js 14 App Router 데모 화면 (page.tsx 한 장)
samples/         # POST /reports 페이로드 3건 (fraud/spam/abuse)
scripts/demo.sh  # 1~6단계 한 번에 도는 스모크 데모
docker-compose.yml
docs/            # 기획·요구사항·API·데이터모델·워크플로우 문서
```

## 개발 메모

- 코드 변경 후 재기동: `docker compose up -d --build api worker`
- 로그: `docker compose logs -f api worker`
- DB 직접 접근: `docker exec -it report-triage-agent-postgres-1 psql -U triage -d triage`
- 분류·라우팅 규칙은 `backend/app/services/{classifier,priority,review,routing}.py`에서 한 함수씩 나뉘어 있으므로 단위 테스트하기 쉽다.

## 트러블슈팅

실제로 자주 만난 케이스만 추렸다.

- **`/metrics/events`가 빈 배열로 나옴**
  consumer 컨테이너가 안 떠 있을 가능성이 크다. `docker compose ps consumer`로 상태 확인 후 `docker compose logs consumer --tail 30`. publish는 잘 되는데 consumer만 죽어있으면 JetStream에 메시지가 쌓여 있다가 consumer가 다시 뜨면 한 번에 드레인된다.

- **첫 빌드 직후 worker가 `temporal:7233 connection refused` 로 재시작 루프**
  Temporal `auto-setup`이 Postgres 스키마 구성에 ~15초 걸리고 그동안 7233은 listen 전이다. compose healthcheck가 `start_period: 20s`로 흡수하지만 그래도 worker가 먼저 떴다면 단순히 기다리거나 `docker compose restart worker`.

- **frontend 화면이 stale data로 멈춤**
  page.tsx는 client-side fetch + `cache: "no-store"`라 새로고침이면 항상 최신이다. 그래도 이상하면 `docker compose restart frontend` (Next dev 서버 HMR 캐시 리셋).

- **큐 GET에 cursor 넣었는데 `400 invalid cursor`**
  ISO8601의 `+00:00`이 URL에서 공백으로 디코드돼서 깨진다. `--data-urlencode "cursor=$NEXT"` 형태로 percent-encode 필수 (§4 예시 참고).

## 범위 밖

인증, 운영자 할당/처리 UI, 정책 룰 에디터, 모델 학습, 벡터 검색, 실시간 대시보드, 외부 시스템 연동, 부하 테스트는 MVP에서 제외 (`docs/02-mvp-scope.md`).
