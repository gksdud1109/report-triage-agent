from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TargetType = Literal["listing", "user", "chat_message", "post", "comment", "transaction"]
ReasonCode = Literal[
    "spam", "fraud_suspected", "abusive_language", "policy_violation", "scam_link", "other"
]
SourceChannel = Literal["marketplace", "community", "chat", "profile"]
ReportStatus = Literal["queued", "processing", "classified", "failed"]


class ReportPayload(BaseModel):
    reporter_id: str
    target_type: TargetType
    target_id: str
    reason_code: ReasonCode
    description: str
    source_channel: SourceChannel
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportCreateRequest(ReportPayload):
    @field_validator("description")
    @classmethod
    def _non_empty_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("description must not be empty")
        return v


class ReportCreateResponse(BaseModel):
    report_id: str
    status: ReportStatus


class ClassificationPayload(BaseModel):
    category: Literal["fraud", "spam", "abuse", "policy", "general"]
    priority: Literal["low", "medium", "high", "critical"]
    requires_review: bool
    confidence: float
    reasoning_summary: str
    routed_queue: str


class ReportDetailResponse(BaseModel):
    report_id: str
    status: ReportStatus
    report: ReportPayload
    classification: ClassificationPayload | None = None
    created_at: datetime
    updated_at: datetime


class ReprocessResponse(BaseModel):
    report_id: str
    status: ReportStatus
    message: str = "reprocess requested"
