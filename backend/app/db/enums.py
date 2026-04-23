"""상태 문자열을 한 곳에 모은다.

매직 스트링이 reports.py / activities.py / repo.py / 테스트에 흩어지면
typo 1글자에 운영 사고가 난다. StrEnum은 Pydantic v2 / SQLAlchemy / json
직렬화 모두에서 문자열로 동작하므로 DB 컬럼 타입(String(16))을 그대로 두고
사용처만 enum 멤버로 교체할 수 있다.
"""

from enum import StrEnum


class ReportStatus(StrEnum):
    """`reports.status` 가 가질 수 있는 값.

    상태 전이는 워크플로 활동에서 일어난다 (queued → processing → classified
    또는 → failed). workflow_start_failed는 Temporal start_workflow 자체가 실패한
    경우만 사용 — "분류는 시도조차 안 됐다"는 의미를 GET /reports에서 즉시 식별
    가능하게 한다.
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    FAILED = "failed"
    WORKFLOW_START_FAILED = "workflow_start_failed"
