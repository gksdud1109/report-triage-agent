"""classifier 규칙 단위 테스트.

규칙 우선순위(fraud > abuse > spam > policy > scam_link > general)와
reason_code/키워드 두 경로 모두를 다룬다.
"""

from app.services.classifier import classify_report


def test_fraud_via_reason_code() -> None:
    r = classify_report("fraud_suspected", "그냥 직거래", {})
    assert r.category == "fraud"
    assert r.confidence >= 0.85  # reason_code 직접 매칭은 더 높은 confidence


def test_fraud_via_description_keyword() -> None:
    r = classify_report("other", "선입금부터 보내달라고 했어요", {})
    assert r.category == "fraud"
    assert 0.6 < r.confidence < 0.85  # 키워드 매칭은 약한 신호


def test_abuse_keyword_in_metadata() -> None:
    r = classify_report("other", "내용 없음", {"snippet": "씨발 협박 메시지"})
    assert r.category == "abuse"


def test_spam_via_reason_code() -> None:
    r = classify_report("spam", "그냥 광고", {})
    assert r.category == "spam"


def test_policy_via_keyword() -> None:
    r = classify_report("other", "의약품을 무허가로 판매하고 있어요", {})
    assert r.category == "policy"


def test_scam_link_reason_code_routes_to_fraud() -> None:
    r = classify_report("scam_link", "https://bad.example", {})
    assert r.category == "fraud"


def test_general_fallback_for_weak_signal() -> None:
    r = classify_report("other", "그냥 신고합니다", {})
    assert r.category == "general"
    assert r.confidence < 0.5
