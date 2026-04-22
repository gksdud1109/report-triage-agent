# 제품 요구사항

## 1. 기능 요구사항

### FR-1 신고 생성

- 사용자는 신고 원본을 API로 전송할 수 있어야 한다.
- 신고 요청에는 아래 필드가 포함되어야 한다.
  - `reporter_id`
  - `target_type`
  - `target_id`
  - `reason_code`
  - `description`
  - `source_channel`
  - `metadata`
- 서버는 신고를 저장하고 `report_id`를 반환해야 한다.
- 서버는 workflow 시작 실패 여부와 무관하게 저장 성공/실패를 분리해서 다뤄야 한다.

### FR-2 신고 상태 추적

- 신고는 아래 상태를 가진다.
  - `queued`
  - `processing`
  - `classified`
  - `failed`
- API 사용자는 현재 상태를 조회할 수 있어야 한다.
- **status의 단일 진실 원본은 `reports.status` (DB)이다.** API는 Temporal workflow execution 상태를 직접 참조하지 않고 DB만 읽는다. Temporal 상태는 운영/관측 보조 용도로만 사용한다.

### FR-3 자동 분류

- 시스템은 신고의 category를 1개 선택해야 한다.
- 분류 로직은 추후 LLM으로 대체 가능해야 한다.
- 초기에 규칙 기반 분류로 구현해도 괜찮다.

### FR-4 우선순위 계산

- 시스템은 운영 대응 우선순위를 계산해야 한다.
- 사기 의심, 반복 신고, 거래 관련 신고 등은 더 높은 우선순위를 받을 수 있다.

### FR-5 review 여부 판단

- 시스템은 사람 검토 필요 여부를 boolean으로 결정해야 한다.
- low confidence 또는 고위험 category는 `requires_review=true`가 되어야 한다.

### FR-6 운영 큐 라우팅

- 시스템은 분류 결과를 바탕으로 큐 이름을 결정해야 한다.
- queue item은 별도 테이블로 저장해야 한다.
- MVP 카테고리 → 큐 매핑은 아래로 고정한다.
  - `fraud` → `fraud-review`
  - `spam` → `spam-review`
  - `abuse` → `abuse-review`
  - `policy` → `general-review` (전용 정책 검토 큐는 MVP 범위 밖이므로 일반 큐로 합류)
  - `general` → `general-review`

### FR-7 결과 조회

- 신고 단건 조회 시 아래를 확인할 수 있어야 한다.
  - 신고 원본
  - 현재 상태
  - 분류 결과
  - routed queue
- 큐 목록 조회 시 해당 queue에 속한 신고들의 요약 목록을 볼 수 있어야 한다.

### FR-8 재처리

- `POST /reports/{report_id}/reprocess`로 재처리를 요청할 수 있어야 한다.
- MVP에서는 "최신 결과 1개만 유지" 방식으로 단순화한다.
- 구체 동작은 아래와 같다.
  - `reports.status`를 `queued`로 되돌린다.
  - 새로운 Temporal run을 시작한다. (workflow_id 전략은 `06-workflow-and-events.md` 참고)
  - `report_classifications`와 `review_queue_items`는 `report_id` 기준 **upsert-overwrite**로 최신 결과만 남긴다.
  - 분류·큐 라우팅 이력 테이블은 두지 않는다. 필요해지면 별도 테이블로 확장한다.

## 2. 비기능 요구사항

### NFR-1 구현 단순성

- 1~2일 내에 구현 가능해야 한다.
- 로컬 개발 환경에서 재현 가능해야 한다.

### NFR-2 상태 복원 가능성

- 장기 실행 흐름은 프로세스 재시작 후에도 추적 가능해야 한다.
- 이 요구사항 때문에 background task보다 Temporal workflow가 우선이다.

### NFR-3 느슨한 결합

- 후속 운영 시스템은 FastAPI API 호출 없이 이벤트를 구독할 수 있어야 한다.
- 이 요구사항 때문에 JetStream을 사용한다.

### NFR-4 설명 가능성

- README만 읽고도 왜 이 구조를 선택했는지 설명 가능해야 한다.
- 면접에서 3분 내로 아키텍처를 설명할 수 있어야 한다.

### NFR-5 테스트 용이성

- 분류 로직은 독립 함수나 activity로 분리해 단위 테스트하기 쉬워야 한다.
- workflow는 최소한 happy path 테스트가 가능해야 한다.

## 3. 입력 데이터 요구사항

### target_type 후보

- `listing`
- `user`
- `chat_message`
- `post`
- `comment`
- `transaction`

### reason_code 후보

- `spam`
- `fraud_suspected`
- `abusive_language`
- `policy_violation`
- `scam_link`
- `other`

### source_channel 후보

- `marketplace`
- `community`
- `chat`
- `profile`

## 4. 분류 규칙 초안

초기 MVP에서는 아래처럼 단순 규칙 기반 분류를 허용한다.

- `reason_code=fraud_suspected` 또는 description에 "선입금", "예약금", "외부 메신저"가 포함되면 `fraud`
- `reason_code=spam` 또는 description에 광고/도배 패턴이 보이면 `spam`
- 욕설, 협박, 혐오 표현 키워드가 있으면 `abuse`
- 그 외는 `general`

priority 예시 규칙:

- `fraud`는 기본 `high`
- 금전, 외부 링크, 반복 신고 힌트가 있으면 `critical`
- `abuse`는 기본 `medium`
- `spam`은 기본 `medium`
- 정보 부족 시 `low`

requires_review 예시 규칙:

- `priority`가 `high` 이상이면 `true`
- 분류 confidence가 낮으면 `true`
- `general`이면서 confidence가 높으면 `false`

## 5. 에러 처리 원칙

- 입력 검증 실패는 `400`
- 존재하지 않는 신고 조회는 `404`
- workflow 시작 실패는 `500` 또는 `503`
- activity 실패는 workflow retry로 우선 처리한다.
- 최종 실패 시 `reports.status=failed`를 남긴다.

## 6. 구현 시 주의사항

- 사용자 입력 reason과 시스템 분류 category를 같은 값으로 취급하지 않는다.
- `metadata`는 JSON 컬럼으로 시작하고 과도한 정규화는 피한다.
- queue 라우팅 로직은 함수로 분리해 수정 가능하게 둔다.
- 이후 LLM 분류를 붙일 수 있게 classifier 인터페이스를 단순하게 유지한다.
