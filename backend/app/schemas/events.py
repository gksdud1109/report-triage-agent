from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TriagedEvent(BaseModel):
    event_type: Literal["report.triaged"] = "report.triaged"
    report_id: str
    category: str
    priority: str
    requires_review: bool
    confidence: float
    occurred_at: datetime


class QueueRoutedEvent(BaseModel):
    event_type: Literal["queue.routed"] = "queue.routed"
    report_id: str
    queue_name: str
    queue_status: str
    occurred_at: datetime
