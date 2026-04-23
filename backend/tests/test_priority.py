"""priority 결정 단위 테스트.

규칙: fraud + (money|external_link) → critical, fraud 단독 → high,
policy → high, abuse/spam → medium, general → 신호 유무에 따라 medium/low.
"""

from app.services.priority import score_priority


def test_fraud_with_money_signal_in_text_is_critical() -> None:
    assert score_priority("fraud", "선입금부터 보내달라고", {}) == "critical"


def test_fraud_with_price_metadata_is_critical() -> None:
    """텍스트에 돈 키워드가 없어도 metadata.price가 있으면 money signal로 본다."""
    assert score_priority("fraud", "직거래 사기 같음", {"price": 300000}) == "critical"


def test_fraud_with_external_link_is_critical() -> None:
    assert score_priority("fraud", "카톡으로 이동하자고 함", {}) == "critical"


def test_fraud_without_any_signal_is_high() -> None:
    assert score_priority("fraud", "사기인 것 같아요", {}) == "high"


def test_policy_is_always_high() -> None:
    assert score_priority("policy", "금지 품목 판매", {}) == "high"


def test_abuse_is_medium() -> None:
    assert score_priority("abuse", "욕설 신고", {}) == "medium"


def test_spam_is_medium() -> None:
    assert score_priority("spam", "광고 도배", {}) == "medium"


def test_general_with_money_signal_promoted_to_medium() -> None:
    assert score_priority("general", "송금 요구가 있었어요", {}) == "medium"


def test_general_without_signal_is_low() -> None:
    assert score_priority("general", "그냥 신고합니다", {}) == "low"
