# MVP 범위

## 포함 범위

### 1. 신고 접수

- `POST /reports`로 신고를 생성한다.
- 신고 원본은 `reports` 테이블에 저장한다.
- 신고 생성 직후 status는 `queued`로 시작한다.
- API는 triage workflow를 비동기로 시작한다.

### 2. 1차 자동 분류

- 신고 사유, 설명, 메타데이터를 바탕으로 category를 결정한다.
- 초기 category 후보는 아래로 제한한다.
  - `fraud`
  - `spam`
  - `abuse`
  - `policy`
  - `general`

### 3. 우선순위 산정

- 신고 내용과 분류 결과를 바탕으로 priority를 산정한다.
- priority는 아래로 제한한다.
  - `low`
  - `medium`
  - `high`
  - `critical`

### 4. review 필요 여부 판단

- 완전 자동 처리 여부를 판단하지는 않는다.
- MVP에서는 `requires_review`를 계산하고 운영 큐로 보내는 것까지만 수행한다.

### 5. 운영 큐 라우팅

- 분류 결과에 따라 운영 큐를 하나 선택한다.
- 초기 queue 후보는 아래로 제한한다.
  - `fraud-review`
  - `spam-review`
  - `abuse-review`
  - `general-review`

### 6. 결과 조회

- `GET /reports/{report_id}`로 신고 원본과 분류 결과를 조회한다.
- `GET /queues/{queue_name}/reports`로 큐별 목록을 조회한다.

### 7. 이벤트 발행

- triage 완료 시 NATS JetStream에 이벤트를 발행한다.
- 최소 2개 subject를 운영한다.
  - `report.triaged`
  - `queue.routed`

## 제외 범위

- 로그인, 인증, RBAC
- 운영자 할당/처리 완료 UI
- 실제 제재 실행
- 정책 룰 에디터
- 모델 학습 파이프라인
- 벡터 검색/유사 신고 탐지
- 실시간 웹소켓 대시보드
- Slack, 메일, 외부 티켓 시스템 연동
- 대용량 부하 테스트

## 1~2일 MVP 완료 기준

- 로컬에서 `docker compose up`으로 핵심 컴포넌트가 뜬다.
- 신고 생성부터 결과 저장까지 end-to-end가 재현된다.
- 최소 3개의 샘플 신고를 넣어 서로 다른 큐로 라우팅되는 것을 확인할 수 있다.
- README와 `docs/`만 읽어도 구조와 의사결정을 설명할 수 있다.

## 범위 통제 원칙

- 프론트는 데모 용도로만 만든다.
- AI 정확도보다 상태 흐름과 책임 분리를 우선한다.
- activity 개수는 4~6개 수준으로 유지한다.
- DB 테이블은 최소 3개만 사용한다.
- 이벤트 소비자는 없어도 되지만, 있더라도 단순 로그/집계 수준 1개만 둔다.
