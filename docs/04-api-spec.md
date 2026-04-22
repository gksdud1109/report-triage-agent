# API 스펙

## 1. `POST /reports`

신고를 생성하고 triage workflow를 시작한다.

### Request

```json
{
  "reporter_id": "user_123",
  "target_type": "listing",
  "target_id": "listing_456",
  "reason_code": "fraud_suspected",
  "description": "선입금을 유도하고 외부 메신저로 이동하자고 했습니다.",
  "source_channel": "marketplace",
  "metadata": {
    "listing_title": "아이폰 15 미개봉",
    "price": 300000,
    "chat_excerpt": "예약금 먼저 보내주세요",
    "target_user_id": "user_999"
  }
}
```

### Response `202 Accepted`

```json
{
  "report_id": "rpt_001",
  "status": "queued"
}
```

### Validation rules

- `description`은 빈 문자열이면 안 된다.
- `target_type`, `reason_code`, `source_channel`은 허용된 enum 중 하나여야 한다.
- `metadata`는 선택이지만 JSON object 형태를 권장한다.

## 2. `GET /reports/{report_id}`

신고 상세와 분류 결과를 조회한다.

### Response `200 OK`

```json
{
  "report_id": "rpt_001",
  "status": "classified",
  "report": {
    "reporter_id": "user_123",
    "target_type": "listing",
    "target_id": "listing_456",
    "reason_code": "fraud_suspected",
    "description": "선입금을 유도하고 외부 메신저로 이동하자고 했습니다.",
    "source_channel": "marketplace",
    "metadata": {
      "listing_title": "아이폰 15 미개봉",
      "price": 300000
    }
  },
  "classification": {
    "category": "fraud",
    "priority": "high",
    "requires_review": true,
    "confidence": 0.88,
    "reasoning_summary": "선입금 요구와 외부 메신저 이동 패턴이 확인됨",
    "routed_queue": "fraud-review"
  }
}
```

## 3. `GET /queues/{queue_name}/reports`

큐별 신고 목록을 조회한다.

### Query params

- `status`
- `limit`
- `cursor`

### Example response `200 OK`

```json
{
  "queue_name": "fraud-review",
  "items": [
    {
      "report_id": "rpt_001",
      "queue_status": "pending",
      "category": "fraud",
      "priority": "high",
      "requires_review": true,
      "enqueued_at": "2026-04-22T12:00:00Z"
    }
  ],
  "next_cursor": null
}
```

## 4. `POST /reports/{report_id}/reprocess`

기존 신고를 다시 분류한다.

### Response `202 Accepted`

```json
{
  "report_id": "rpt_001",
  "status": "queued",
  "message": "reprocess requested"
}
```

## 5. `GET /health`

### Response `200 OK`

```json
{
  "status": "ok"
}
```

## 6. 오류 응답 형식

가능하면 FastAPI 기본 에러 형식을 유지해도 된다. 다만 아래 공통 필드는 있으면 좋다.

```json
{
  "detail": "report not found"
}
```

## 7. Pydantic 모델 제안

### ReportCreateRequest

- `reporter_id: str`
- `target_type: Literal[...]`
- `target_id: str`
- `reason_code: Literal[...]`
- `description: str`
- `source_channel: Literal[...]`
- `metadata: dict[str, Any] = {}`

### ReportDetailResponse

- `report_id: str`
- `status: str`
- `report: ReportPayload`
- `classification: ClassificationPayload | None`

### QueueListResponse

- `queue_name: str`
- `items: list[QueueItemPayload]`
- `next_cursor: str | None`
