"""NATS JetStream 스트림 및 subject 정의.

JetStream은 후속 소비자로 결과를 전달하는 얇은 경계로만 사용한다.
단일 스트림 아래 2개 subject(triaged, routed)만 운영한다.

duplicate_window: publisher-side dedup window (초 단위 float). publish 활동이
워크플로 retry로 재실행될 때 같은 (subject, report_id)에 대한 두 번째 publish는
이 window 안에서는 JetStream이 자동으로 무시한다 (events.py에서 `Nats-Msg-Id`
헤더를 함께 넣어야 동작). 120초면 단일 워크플로의 재시도 누적
(_DEFAULT_RETRY: 3회 × 최대 15s)을 충분히 덮는다.
"""

SUBJECT_REPORT_TRIAGED = "report.triaged"
SUBJECT_QUEUE_ROUTED = "queue.routed"

STREAM_SUBJECTS = [SUBJECT_REPORT_TRIAGED, SUBJECT_QUEUE_ROUTED]

DUPLICATE_WINDOW_SECONDS: float = 120.0
