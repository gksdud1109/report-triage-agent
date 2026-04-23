"""pytest 설정.

이 프로젝트의 테스트는 두 종류로 나뉜다.

- 순수 함수 테스트(`test_classifier`/`test_routing`/`test_priority`/`test_review`)
  → 의존성 없음, 빠르게 돈다.
- 워크플로 테스트(`test_workflow`)
  → Temporal `start_time_skipping` 환경에 가짜 activity를 주입한다.
    첫 실행 시 `~/.temporalio/` 아래로 test-server 바이너리를 다운받는다.
"""

import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """워크플로 테스트가 동일 loop에서 client/worker를 공유하도록 session 단위로 묶는다."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()
