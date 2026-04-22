## 프로젝트 기획

커뮤니티/중고거래 서비스에서는 스팸, 사기, 어뷰징, 정책 위반 신고가 지속적으로 들어오고, 운영팀은 제한된 리소스로 우선순위가 높은 건부터 빠르게 검토해야 합니다.

이 프로젝트는 사용자 신고를 입력받아 AI와 규칙 기반 로직으로 1차 분류하고, 우선순위와 검토 필요 여부를 판단해 운영 큐로 라우팅하는 운영 자동화 MVP입니다.

FastAPI는 신고 접수와 조회 API를 담당하고, Temporal은 분류부터 큐 배정까지의 비동기 워크플로우를 관리하며, NATS JetStream은 분류 결과를 후속 운영 시스템으로 전달하는 이벤트 채널로 사용합니다.  
목표는 높은 정확도의 모델을 만드는 것이 아니라, 운영 가능한 신고 triage 흐름을 작은 서비스로 설계하고 구현하는 것입니다.

## MVP 범위

- 신고 생성 API 제공
- 신고 본문과 메타데이터를 기반으로 1차 분류 수행
- `category`, `priority`, `requires_review` 판단
- Temporal workflow로 분류, 판단, 큐 라우팅 단계 분리
- 운영 큐(`fraud`, `spam`, `abuse`, `general`) 중 하나로 배정
- 분류 결과 조회 API 및 큐별 목록 조회 API 제공
- NATS JetStream으로 분류 완료 / 큐 라우팅 이벤트 발행

## 제외 범위

- 운영자 인증/권한 관리
- 정교한 정책 룰 엔진
- 실시간 대시보드 고도화
- 실제 대규모 트래픽 처리
- 멀티모달 AI 분류
- 운영자 액션 이력 및 감사 로그 고도화

## 문서

- [docs/README.md](/Users/hanyoung-jeong/Development/report-triage-agent/docs/README.md)
- [MVP 범위](/Users/hanyoung-jeong/Development/report-triage-agent/docs/02-mvp-scope.md)
- [요구사항](/Users/hanyoung-jeong/Development/report-triage-agent/docs/03-product-requirements.md)
- [API 스펙](/Users/hanyoung-jeong/Development/report-triage-agent/docs/04-api-spec.md)
- [데이터 모델](/Users/hanyoung-jeong/Development/report-triage-agent/docs/05-data-model.md)
- [Workflow / 이벤트 설계](/Users/hanyoung-jeong/Development/report-triage-agent/docs/06-workflow-and-events.md)
