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

종료:

```bash
docker compose down       # DB 유지
docker compose down -v    # 초기화
```

## 동작 검증

### 1. 헬스체크

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 2. 샘플 3건 — 서로 다른 큐로 라우팅 확인

```bash
# fraud → fraud-review
curl -sS -X POST http://localhost:8000/reports \
  -H 'content-type: application/json' \
  -d '{
    "reporter_id": "user_123", "target_type": "listing", "target_id": "listing_456",
    "reason_code": "fraud_suspected",
    "description": "선입금을 유도하고 외부 메신저로 이동하자고 했습니다.",
    "source_channel": "marketplace",
    "metadata": {"price": 300000}
  }'

# spam → spam-review
curl -sS -X POST http://localhost:8000/reports \
  -H 'content-type: application/json' \
  -d '{
    "reporter_id": "user_222", "target_type": "post", "target_id": "post_999",
    "reason_code": "spam",
    "description": "광고 도배 반복 게시물입니다.",
    "source_channel": "community", "metadata": {}
  }'

# abuse → abuse-review
curl -sS -X POST http://localhost:8000/reports \
  -H 'content-type: application/json' \
  -d '{
    "reporter_id": "user_333", "target_type": "chat_message", "target_id": "msg_777",
    "reason_code": "abusive_language",
    "description": "심한 욕설과 협박을 했습니다.",
    "source_channel": "chat", "metadata": {}
  }'
```

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

## API 요약

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET`  | `/health` | 헬스체크 |
| `POST` | `/reports` | 신고 생성 + workflow 시작 (202) |
| `GET`  | `/reports/{report_id}` | 신고 + 분류 결과 조회 |
| `POST` | `/reports/{report_id}/reprocess` | 재처리 시작 (202, 어떤 상태에서도 즉시 가능) |
| `GET`  | `/queues/{queue_name}/reports` | 큐별 신고 요약 목록 (커서 페이지네이션) |

상세 스펙: [`docs/04-api-spec.md`](./docs/04-api-spec.md)

## 설계 의사결정

- **FastAPI는 얇게.** 라우터는 입력 검증·DB 저장·workflow 시작만 담당한다. 장기 실행 흐름은 Temporal로 넘긴다.
- **장기 흐름은 Temporal workflow.** background task를 안 쓴 이유는 프로세스 재시작 후에도 추적 가능해야 하고(NFR-2), 단계별 retry/fallback이 필요하기 때문이다.
- **NATS JetStream은 "후속 시스템 경계".** 핵심 처리 엔진이 아니라 다운스트림 소비자가 FastAPI 호출 없이 결과를 받아갈 수 있게 하는 비동기 경계로 사용한다(NFR-3).
- **`reports.status`가 단일 진실 원본.** API는 Temporal workflow execution 상태를 직접 참조하지 않는다. activity가 DB에 상태를 기록하고, API는 DB만 읽는다 (`docs/03-product-requirements.md` FR-2).
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
    messaging/   # NATS JetStream 어댑터
    temporal/    # workflow / activity / client / worker
    main.py      # FastAPI 앱 + lifespan
  Dockerfile
  scripts/init-db.sh  # postgres 초기화 시 temporal DB 생성
docker-compose.yml
docs/            # 기획·요구사항·API·데이터모델·워크플로우 문서
```

## 개발 메모

- 코드 변경 후 재기동: `docker compose up -d --build api worker`
- 로그: `docker compose logs -f api worker`
- DB 직접 접근: `docker exec -it report-triage-agent-postgres-1 psql -U triage -d triage`
- 분류·라우팅 규칙은 `backend/app/services/{classifier,priority,review,routing}.py`에서 한 함수씩 나뉘어 있으므로 단위 테스트하기 쉽다.

## 범위 밖

인증, 운영자 할당/처리 UI, 정책 룰 에디터, 모델 학습, 벡터 검색, 실시간 대시보드, 외부 시스템 연동, 부하 테스트는 MVP에서 제외 (`docs/02-mvp-scope.md`).
