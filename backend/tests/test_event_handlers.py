"""JetStream 이벤트 핸들러 — decode/dispatch 단위 테스트.

`record_event`는 Postgres 전용 ON CONFLICT 구문이라 단위 테스트에서
실 DB를 띄우지 않는다 (sqlite는 dialect가 다름). 대신 dispatch 경로
(decode_subject)에 대해 화이트리스트/payload 검증만 검증한다.
"""

from app.messaging.handlers import KNOWN_SUBJECTS, decode_subject
from app.messaging.streams import SUBJECT_QUEUE_ROUTED, SUBJECT_REPORT_TRIAGED


def test_known_subjects_set_matches_stream_definition() -> None:
    assert KNOWN_SUBJECTS == {SUBJECT_REPORT_TRIAGED, SUBJECT_QUEUE_ROUTED}


def test_decode_returns_subject_for_valid_payload() -> None:
    assert decode_subject(SUBJECT_REPORT_TRIAGED, b'{"report_id":"rpt_x"}') == SUBJECT_REPORT_TRIAGED
    assert decode_subject(SUBJECT_QUEUE_ROUTED, b'{}') == SUBJECT_QUEUE_ROUTED


def test_decode_rejects_unknown_subject() -> None:
    assert decode_subject("report.unknown", b'{}') is None


def test_decode_rejects_malformed_json() -> None:
    assert decode_subject(SUBJECT_REPORT_TRIAGED, b'not json') is None


def test_decode_rejects_non_utf8_bytes() -> None:
    # invalid UTF-8 sequence
    assert decode_subject(SUBJECT_REPORT_TRIAGED, b'\xff\xfe\x00') is None
