HIGH_RISK_CATEGORIES = {"fraud", "policy"}
HIGH_PRIORITY_LEVELS = {"high", "critical"}
LOW_CONFIDENCE_THRESHOLD = 0.6


def decide_requires_review(category: str, priority: str, confidence: float) -> bool:
    if priority in HIGH_PRIORITY_LEVELS:
        return True
    if category in HIGH_RISK_CATEGORIES:
        return True
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return True
    return False
