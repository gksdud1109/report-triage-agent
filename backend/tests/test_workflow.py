"""ReportTriageWorkflow happy-path 통합 테스트.

Temporal `start_time_skipping` 환경에 가짜 activity(같은 이름, canned 응답)를
주입해 워크플로의 단계 순서 + 상태 전파가 깨지지 않는지만 본다.
DB/NATS는 닿지 않는다.
"""

import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.temporal.workflows import ReportTriageWorkflow


CALLED: list[str] = []


@activity.defn(name="load_report_activity")
async def fake_load(report_id: str) -> dict:
    CALLED.append("load")
    return {
        "report_id": report_id,
        "reason_code": "spam",
        "description": "광고 도배 반복 게시물",
        "metadata": {},
    }


@activity.defn(name="mark_report_processing_activity")
async def fake_mark_processing(report_id: str) -> None:
    CALLED.append("mark_processing")


@activity.defn(name="classify_report_activity")
async def fake_classify(report: dict) -> dict:
    CALLED.append("classify")
    return {"category": "spam", "confidence": 0.75, "reasoning_summary": "fake"}


@activity.defn(name="score_priority_activity")
async def fake_priority(report: dict, category: str) -> str:
    CALLED.append("priority")
    return "medium"


@activity.defn(name="decide_review_activity")
async def fake_review(category: str, priority_level: str, confidence: float) -> bool:
    CALLED.append("review")
    return False


@activity.defn(name="persist_classification_activity")
async def fake_persist(
    report_id: str,
    category: str,
    priority_level: str,
    requires_review: bool,
    confidence: float,
    reasoning_summary: str,
) -> str:
    CALLED.append("persist")
    return "spam-review"  # routing 결과 = queue_name


@activity.defn(name="route_queue_activity")
async def fake_route(report_id: str, queue_name: str) -> None:
    CALLED.append("route")


@activity.defn(name="publish_triage_events_activity")
async def fake_publish(
    report_id: str,
    category: str,
    priority_level: str,
    requires_review: bool,
    confidence: float,
    queue_name: str,
) -> None:
    CALLED.append("publish")


@activity.defn(name="mark_report_classified_activity")
async def fake_mark_classified(report_id: str) -> None:
    CALLED.append("mark_classified")


@activity.defn(name="mark_report_failed_activity")
async def fake_mark_failed(report_id: str) -> None:
    CALLED.append("mark_failed")


FAKE_ACTIVITIES = [
    fake_load,
    fake_mark_processing,
    fake_classify,
    fake_priority,
    fake_review,
    fake_persist,
    fake_route,
    fake_publish,
    fake_mark_classified,
    fake_mark_failed,
]


@pytest.mark.asyncio
async def test_workflow_happy_path_invokes_activities_in_order_and_returns_summary() -> None:
    CALLED.clear()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = f"test-tq-{uuid.uuid4().hex[:8]}"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[ReportTriageWorkflow],
            activities=FAKE_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                ReportTriageWorkflow.run,
                "rpt_test_happy",
                id=f"wf-{uuid.uuid4().hex[:8]}",
                task_queue=task_queue,
            )

    assert result == {
        "report_id": "rpt_test_happy",
        "category": "spam",
        "priority": "medium",
        "requires_review": False,
        "queue_name": "spam-review",
    }
    assert CALLED == [
        "load",
        "mark_processing",
        "classify",
        "priority",
        "review",
        "persist",
        "route",
        "publish",
        "mark_classified",
    ]
    assert "mark_failed" not in CALLED
