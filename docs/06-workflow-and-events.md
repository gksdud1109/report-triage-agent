# Workflow 및 이벤트 설계

## 1. Temporal workflow 책임

workflow 이름:

- `ReportTriageWorkflow`

### workflow_id 전략

- 최초 실행: `report-triage-{report_id}`
- 재처리 실행: `report-triage-{report_id}-{epoch_ms}`
  - 같은 `report_id`로 여러 run이 생길 수 있지만, MVP에서는 DB 쪽 결과가 upsert-overwrite되므로 충돌 없이 "최신 run이 덮어쓰는" 모델이 유지된다.
  - 이전 run을 별도로 cancel하지 않는다. 이전 run이 먼저 완료되어 덮어쓰더라도 곧이어 최신 run이 다시 덮어쓴다.
- workflow 입력: `report_id` 문자열 하나.

### status 소유권

- **`reports.status`가 단일 진실 원본이다.** Temporal workflow execution 상태와는 별개다.
- activity가 상태 전이(`processing`, `classified`, `failed`)를 직접 DB에 기록한다.
- API는 DB의 `reports.status`만 읽고 응답한다. Temporal을 describe해서 상태를 만들지 않는다.

workflow는 아래 단계의 순서를 보장하고, 실패 시 재시도 정책을 적용한다.

1. 신고 로드
2. 상태를 `processing`으로 변경
3. 신고 분류
4. 우선순위 계산
5. review 필요 여부 판단
6. 결과 저장
7. 운영 큐 라우팅
8. 이벤트 발행
9. 신고 상태를 `classified`로 변경

## 2. Activity 분리

### `load_report_activity`

- `report_id`로 신고 원본 조회
- 신고가 없으면 non-retryable error

### `mark_report_processing_activity`

- `reports.status=processing` 반영

### `classify_report_activity`

- 입력: 신고 원본
- 출력: `category`, `confidence`, `reasoning_summary`
- 초기 구현은 규칙 기반 또는 mock classifier 가능

### `score_priority_activity`

- 입력: 신고 원본 + category
- 출력: `priority`

### `decide_review_activity`

- 입력: category, priority, confidence
- 출력: `requires_review`

### `persist_classification_activity`

- classification 결과 upsert (report_id 기준 overwrite, 최신 1건만 유지)

### `route_queue_activity`

- queue 이름 결정
- `review_queue_items` upsert (report_id 기준 overwrite)
- 결과 queue 이름 반환

카테고리 → 큐 매핑은 다음과 같이 고정한다.

| category | queue_name |
|---|---|
| `fraud` | `fraud-review` |
| `spam` | `spam-review` |
| `abuse` | `abuse-review` |
| `policy` | `general-review` |
| `general` | `general-review` |

`policy`는 전용 큐를 두지 않고 `general-review`로 합류한다. 향후 정책 검토 데스크가 생기면 `policy-review`를 추가한다.

### `publish_triage_events_activity`

- JetStream에 이벤트 발행
- 최소 2개 이벤트를 발행한다.
  - triaged
  - routed

### `mark_report_classified_activity`

- `reports.status=classified` 반영

## 3. 실패 처리 전략

### retryable

- 일시적 DB 연결 오류
- NATS publish 일시 실패
- 외부 분류기 호출 실패

### non-retryable

- 존재하지 않는 report
- enum/입력 데이터 불일치
- 복구 불가능한 validation 오류

### fallback

- 분류 실패가 반복되면 status를 `failed`로 남긴다.
- 가능하면 `general` queue fallback보다 명시적 실패가 낫다.
- 단, 의도적으로 demo를 부드럽게 만들고 싶다면 `general-review` fallback도 허용 가능하다.

## 4. NATS JetStream 역할

JetStream은 핵심 처리 엔진이 아니라 "후속 소비자에게 결과를 안전하게 전달하는 경계"로 사용한다.

## 5. subject 설계

### `report.triaged`

분류 결과가 생성되었음을 알린다.

예시 payload:

```json
{
  "event_type": "report.triaged",
  "report_id": "rpt_001",
  "category": "fraud",
  "priority": "high",
  "requires_review": true,
  "confidence": 0.88,
  "occurred_at": "2026-04-22T12:00:00Z"
}
```

### `queue.routed`

신고가 특정 운영 큐로 이동했음을 알린다.

예시 payload:

```json
{
  "event_type": "queue.routed",
  "report_id": "rpt_001",
  "queue_name": "fraud-review",
  "queue_status": "pending",
  "occurred_at": "2026-04-22T12:00:01Z"
}
```

## 6. 소비자 설계

MVP에서는 소비자가 없어도 된다. 그래도 하나 둔다면 아래 수준이 적당하다.

- `queue_metrics_consumer`
- 각 queue별 건수를 집계하거나 로그를 남긴다.

이 소비자의 목적은 "JetStream을 왜 넣었는지"를 보여주는 데 있다. 복잡한 비즈니스 처리는 불필요하다.

## 7. Claude용 구현 순서

Claude나 다른 에이전트가 구현할 때는 아래 순서를 권장한다.

1. SQLAlchemy 모델과 migration 작성
2. `POST /reports`, `GET /reports/{id}` 구현
3. Temporal client/worker 연결
4. workflow와 core activities 구현
5. classification 결과 저장 및 queue item 저장
6. `GET /queues/{queue_name}/reports` 구현
7. NATS JetStream bootstrap 및 publish activity 구현
8. reprocess API 추가
9. 샘플 데이터와 README 정리

## 8. 폴더 구조 제안

```text
backend/
  app/
    api/
      reports.py
      queues.py
    db/
      models.py
      session.py
    services/
      classifier.py
      priority.py
      routing.py
    temporal/
      client.py
      worker.py
      workflows.py
      activities.py
    nats/
      client.py
      events.py
      streams.py
    main.py
```
