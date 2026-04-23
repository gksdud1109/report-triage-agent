"""사람 검토 필요 여부 단위 테스트.

규칙: high/critical priority OR fraud/policy 카테고리 OR confidence < 0.6.
"""

from app.services.review import decide_requires_review


def test_high_priority_always_requires_review() -> None:
    assert decide_requires_review("spam", "high", 0.99) is True


def test_critical_priority_always_requires_review() -> None:
    assert decide_requires_review("general", "critical", 0.99) is True


def test_fraud_category_requires_review_even_when_medium_priority_high_confidence() -> None:
    assert decide_requires_review("fraud", "medium", 0.95) is True


def test_policy_category_requires_review() -> None:
    assert decide_requires_review("policy", "medium", 0.95) is True


def test_low_confidence_requires_review() -> None:
    assert decide_requires_review("spam", "low", 0.55) is True


def test_high_confidence_clean_case_does_not_require_review() -> None:
    """spam + medium + high confidence는 자동 처리해도 안전한 경우."""
    assert decide_requires_review("spam", "medium", 0.85) is False
