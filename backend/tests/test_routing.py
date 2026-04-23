"""category → queue 매핑 단위 테스트."""

from app.services.routing import ALLOWED_QUEUES, route_to_queue


def test_each_category_routes_to_expected_queue() -> None:
    assert route_to_queue("fraud") == "fraud-review"
    assert route_to_queue("spam") == "spam-review"
    assert route_to_queue("abuse") == "abuse-review"


def test_policy_collapses_to_general_review() -> None:
    """문서상 정책 큐는 별도지만 MVP에서는 general-review로 합류한다."""
    assert route_to_queue("policy") == "general-review"


def test_general_routes_to_general_review() -> None:
    assert route_to_queue("general") == "general-review"


def test_unknown_category_falls_back_to_general_review() -> None:
    """미래에 새 카테고리가 추가돼도 큐 매핑 누락이 운영 사고로 번지지 않게."""
    assert route_to_queue("unknown") == "general-review"


def test_allowed_queues_set_matches_mapping_values() -> None:
    """ALLOWED_QUEUES가 매핑 값 집합과 동기화돼 있는지 (drift 방지)."""
    assert ALLOWED_QUEUES == {"fraud-review", "spam-review", "abuse-review", "general-review"}
