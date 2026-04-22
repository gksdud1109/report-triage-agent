from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    confidence: float
    reasoning_summary: str


@dataclass(frozen=True)
class TriageResult:
    category: str
    priority: str
    requires_review: bool
    confidence: float
    reasoning_summary: str
    routed_queue: str
