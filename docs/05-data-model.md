# 데이터 모델

## 1. 테이블 개요

MVP에서는 아래 3개 테이블만 사용한다.

- `reports`
- `report_classifications`
- `review_queue_items`

## 2. `reports`

신고 원본과 현재 처리 상태를 저장한다.

### 컬럼 제안

- `id`
- `reporter_id`
- `target_type`
- `target_id`
- `reason_code`
- `description`
- `source_channel`
- `metadata` JSONB
- `status`
- `created_at`
- `updated_at`

### status 후보

- `queued`
- `processing`
- `classified`
- `failed`

## 3. `report_classifications`

시스템이 내린 최신 분류 결과를 저장한다.

### 컬럼 제안

- `id`
- `report_id`
- `category`
- `priority`
- `requires_review`
- `confidence`
- `reasoning_summary`
- `routed_queue`
- `created_at`
- `updated_at`

### 제약

- `report_id`는 `reports.id` FK
- MVP에서는 report당 classification 1건만 유지해도 된다.
- 구현 단순화를 위해 `report_id` unique 제약을 둬도 된다.

## 4. `review_queue_items`

운영 큐에 올라간 아이템을 저장한다.

### 컬럼 제안

- `id`
- `report_id`
- `queue_name`
- `queue_status`
- `assigned_to` nullable
- `enqueued_at`
- `updated_at`

### queue_status 후보

- `pending`
- `assigned`
- `done`

## 5. 엔티티 관계

- report 1건은 classification 1건을 가진다.
- report 1건은 review queue item 1건을 가진다.
- 나중에 이력 관리가 필요하면 classification history 테이블로 확장할 수 있다.

## 6. 샘플 레코드

### reports

```json
{
  "id": "rpt_001",
  "reporter_id": "user_123",
  "target_type": "listing",
  "target_id": "listing_456",
  "reason_code": "fraud_suspected",
  "description": "선입금을 유도하고 외부 메신저로 이동하자고 했습니다.",
  "source_channel": "marketplace",
  "metadata": {
    "listing_title": "아이폰 15 미개봉",
    "price": 300000
  },
  "status": "classified"
}
```

### report_classifications

```json
{
  "report_id": "rpt_001",
  "category": "fraud",
  "priority": "high",
  "requires_review": true,
  "confidence": 0.88,
  "reasoning_summary": "선입금 유도와 외부 메신저 이동이 확인됨",
  "routed_queue": "fraud-review"
}
```

### review_queue_items

```json
{
  "report_id": "rpt_001",
  "queue_name": "fraud-review",
  "queue_status": "pending"
}
```

## 7. 설계 원칙

- 과도한 정규화보다 구현 속도를 우선한다.
- metadata는 JSONB로 저장해 도메인 변경에 유연하게 대응한다.
- enum은 DB enum 또는 문자열 제약 중 구현 편한 방식을 선택한다.
- 재처리 시 기존 queue item을 update할지 새 row를 insert할지는 MVP에서 단순화한다.
- MVP에서는 "최신 상태 1개 유지"가 가장 간단하다.
