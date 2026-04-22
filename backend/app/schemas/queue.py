from datetime import datetime
from typing import Literal

from pydantic import BaseModel

QueueStatus = Literal["pending", "assigned", "done"]


class QueueItemPayload(BaseModel):
    report_id: str
    queue_status: QueueStatus
    category: str
    priority: str
    requires_review: bool
    enqueued_at: datetime


class QueueListResponse(BaseModel):
    queue_name: str
    items: list[QueueItemPayload]
    next_cursor: str | None = None
