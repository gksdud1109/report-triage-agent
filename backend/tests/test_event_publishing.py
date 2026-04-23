"""publisher-side dedup 배선 테스트.

events.publish_*가 JetStream `publish`에 `Nats-Msg-Id` 헤더를 정확히 넘기는지
확인한다. JetStream 자체는 띄우지 않고 jetstream context를 mock으로 대체한다.

이 테스트가 막는 회귀: workflow retry로 인한 double-publish가 카운터를 부풀리는
시나리오 — Msg-Id 헤더가 누락되면 stream의 duplicate_window가 무용지물이 된다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.messaging import events as nats_events
from app.messaging import nats_client
from app.messaging.streams import SUBJECT_QUEUE_ROUTED, SUBJECT_REPORT_TRIAGED
from app.schemas.events import QueueRoutedEvent, TriagedEvent


@pytest.fixture
def fake_jetstream(monkeypatch):
    """nats_client.jetstream()이 mock JetStreamContext를 반환하도록 패치한다."""
    js = SimpleNamespace()
    js.publish = AsyncMock(
        return_value=SimpleNamespace(seq=1, duplicate=False)
    )
    monkeypatch.setattr(nats_client, "jetstream", lambda: js)
    return js


@pytest.mark.asyncio
async def test_publish_triaged_sets_nats_msg_id_header(fake_jetstream) -> None:
    event = TriagedEvent(
        report_id="rpt_abc",
        category="spam",
        priority="medium",
        requires_review=False,
        confidence=0.7,
        occurred_at=datetime.now(timezone.utc),
    )
    await nats_events.publish_triaged(event)

    fake_jetstream.publish.assert_awaited_once()
    args, kwargs = fake_jetstream.publish.call_args
    assert args[0] == SUBJECT_REPORT_TRIAGED
    # 헤더가 빠지면 dedup 윈도우가 동작하지 않는다.
    assert kwargs.get("headers") == {"Nats-Msg-Id": f"{SUBJECT_REPORT_TRIAGED}:rpt_abc"}


@pytest.mark.asyncio
async def test_publish_queue_routed_sets_nats_msg_id_header(fake_jetstream) -> None:
    event = QueueRoutedEvent(
        report_id="rpt_abc",
        queue_name="spam-review",
        queue_status="pending",
        occurred_at=datetime.now(timezone.utc),
    )
    await nats_events.publish_queue_routed(event)

    fake_jetstream.publish.assert_awaited_once()
    args, kwargs = fake_jetstream.publish.call_args
    assert args[0] == SUBJECT_QUEUE_ROUTED
    assert kwargs.get("headers") == {"Nats-Msg-Id": f"{SUBJECT_QUEUE_ROUTED}:rpt_abc"}


@pytest.mark.asyncio
async def test_msg_id_is_stable_per_report_so_workflow_retry_dedups(fake_jetstream) -> None:
    """같은 report에 대해 두 번 publish해도 Msg-Id가 동일해야 한다.

    workflow가 publish_triage_events_activity를 retry해서 같은 report에 대해
    두 번 발행하더라도, JetStream은 같은 Msg-Id를 duplicate_window 안에서
    중복 제거한다. 이 테스트는 publisher가 안정적인 Msg-Id를 만들고 있는지
    검증한다.
    """
    event = TriagedEvent(
        report_id="rpt_retry",
        category="fraud",
        priority="high",
        requires_review=True,
        confidence=0.9,
        occurred_at=datetime.now(timezone.utc),
    )
    await nats_events.publish_triaged(event)
    await nats_events.publish_triaged(event)

    assert fake_jetstream.publish.await_count == 2
    headers_first = fake_jetstream.publish.call_args_list[0].kwargs["headers"]
    headers_second = fake_jetstream.publish.call_args_list[1].kwargs["headers"]
    assert headers_first == headers_second
