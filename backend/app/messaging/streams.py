"""NATS JetStream 스트림 및 subject 정의.

JetStream은 후속 소비자로 결과를 전달하는 얇은 경계로만 사용한다.
단일 스트림 아래 2개 subject(triaged, routed)만 운영한다.
"""

SUBJECT_REPORT_TRIAGED = "report.triaged"
SUBJECT_QUEUE_ROUTED = "queue.routed"

STREAM_SUBJECTS = [SUBJECT_REPORT_TRIAGED, SUBJECT_QUEUE_ROUTED]
