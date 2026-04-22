# Report Triage Agent Docs

이 디렉토리는 프로젝트 기획, MVP 범위, 요구사항, API/데이터 모델, 워크플로우 설계를 구현 관점에서 정리한 문서 모음입니다.

## 문서 목록

- [01-overview.md](/Users/hanyoung-jeong/Development/report-triage-agent/docs/01-overview.md)
  프로젝트 문제 정의, 목표, 아키텍처 방향
- [02-mvp-scope.md](/Users/hanyoung-jeong/Development/report-triage-agent/docs/02-mvp-scope.md)
  MVP 범위, 제외 범위, 완료 기준
- [03-product-requirements.md](/Users/hanyoung-jeong/Development/report-triage-agent/docs/03-product-requirements.md)
  기능 요구사항, 비기능 요구사항, 에러 처리 원칙
- [04-api-spec.md](/Users/hanyoung-jeong/Development/report-triage-agent/docs/04-api-spec.md)
  API 요청/응답 스펙
- [05-data-model.md](/Users/hanyoung-jeong/Development/report-triage-agent/docs/05-data-model.md)
  DB 스키마와 데이터 상태 모델
- [06-workflow-and-events.md](/Users/hanyoung-jeong/Development/report-triage-agent/docs/06-workflow-and-events.md)
  Temporal workflow/activity 책임과 NATS JetStream 이벤트 설계

## 구현 우선순위

1. `POST /reports`로 신고를 저장하고 triage workflow를 시작한다.
2. workflow에서 분류, 우선순위 산정, review 필요 여부 판단, queue 라우팅을 수행한다.
3. 결과를 DB에 저장하고 `GET /reports/{id}`로 조회 가능하게 한다.
4. `GET /queues/{queue_name}/reports`로 큐별 목록을 제공한다.
5. 분류 완료 및 큐 라우팅 이벤트를 NATS JetStream에 발행한다.

## 구현 원칙

- 정확한 AI 모델보다 운영 가능한 처리 흐름을 우선한다.
- 분류 로직은 초기에 규칙 기반 또는 mock LLM으로 시작해도 된다.
- FastAPI는 얇게 유지하고 장기 실행/재시도 흐름은 Temporal로 넘긴다.
- NATS JetStream은 "후속 시스템으로 이벤트를 안전하게 전달한다"는 역할에 집중한다.
- README에는 과장된 표현보다 왜 이 구조를 선택했는지를 짧고 명확하게 남긴다.
