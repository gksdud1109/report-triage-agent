"""카테고리 -> 운영 큐 매핑.

문서에는 큐 4개(fraud/spam/abuse/general-review), 카테고리 5개가 정의되어 있다.
MVP에서는 `policy` 전용 큐를 두지 않고 `general-review`로 합류시킨다.
정책 검토 데스크가 생기면 `policy-review`를 추가하면 된다.
"""

_CATEGORY_TO_QUEUE = {
    "fraud": "fraud-review",
    "spam": "spam-review",
    "abuse": "abuse-review",
    "policy": "general-review",
    "general": "general-review",
}

ALLOWED_QUEUES = frozenset(_CATEGORY_TO_QUEUE.values())


def route_to_queue(category: str) -> str:
    return _CATEGORY_TO_QUEUE.get(category, "general-review")
