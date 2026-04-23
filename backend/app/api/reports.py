"""신고 생성/조회 API.

라우터는 얇게 유지한다:
 - 입력 검증과 DB 저장
 - Temporal workflow 시작
 - DB 기준의 종단 상태를 응답으로 변환
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

from app.api.deps import get_session, get_temporal_client
from app.core.config import get_settings
from app.core.ids import new_report_id
from app.db.enums import ReportStatus
from app.db.models import Report
from app.schemas.reports import (
    ClassificationPayload,
    ReportCreateRequest,
    ReportCreateResponse,
    ReportDetailResponse,
    ReportPayload,
    ReprocessResponse,
)
from app.services import reports_repo
from app.temporal.workflows import ReportTriageWorkflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_payload(report: Report) -> ReportPayload:
    return ReportPayload(
        reporter_id=report.reporter_id,
        target_type=report.target_type,
        target_id=report.target_id,
        reason_code=report.reason_code,
        description=report.description,
        source_channel=report.source_channel,
        metadata=report.report_metadata or {},
    )


def _to_classification(report: Report) -> ClassificationPayload | None:
    cls = report.classification
    if cls is None:
        return None
    return ClassificationPayload(
        category=cls.category,
        priority=cls.priority,
        requires_review=cls.requires_review,
        confidence=cls.confidence,
        reasoning_summary=cls.reasoning_summary,
        routed_queue=cls.routed_queue,
    )


@router.post(
    "",
    response_model=ReportCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_report(
    payload: ReportCreateRequest,
    session: AsyncSession = Depends(get_session),
    temporal: Client = Depends(get_temporal_client),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ReportCreateResponse:
    """신고 1건을 저장하고 ReportTriageWorkflow를 시작한다.

    저장 성공/workflow 시작은 분리해서 다룬다. workflow 시작이 실패하면
    DB는 유지하고 503으로 응답해 사용자가 재처리 API로 다시 시도할 수 있다.

    Idempotency-Key:
        클라이언트가 네트워크 오류 등으로 같은 신고를 두 번 POST할 때 두 번째
        요청이 새 row를 만들지 않고 기존 report_id를 그대로 돌려준다. 헤더가
        없으면 기존 동작 유지(매 요청 새 row). 동시 요청 race는 unique 제약
        위반(IntegrityError)을 catch해서 다시 lookup하는 패턴으로 흡수한다.
    """
    settings = get_settings()

    # Idempotency 1차 lookup: 이미 같은 키로 만들어진 게 있으면 그대로 응답.
    if idempotency_key is not None:
        existing = await reports_repo.find_report_by_idempotency_key(
            session, idempotency_key
        )
        if existing is not None:
            return ReportCreateResponse(
                report_id=existing.id, status=existing.status
            )

    report_id = new_report_id()

    try:
        await reports_repo.create_report(
            session, report_id, payload, idempotency_key=idempotency_key
        )
        await session.commit()
    except IntegrityError:
        # 동시 요청이 같은 idempotency_key로 먼저 insert한 경우.
        # 1차 lookup 이후 ~ commit 사이의 race를 흡수: 한 번 더 lookup해서
        # 우승한 쪽 결과를 그대로 돌려준다.
        await session.rollback()
        if idempotency_key is None:
            raise  # idempotency_key와 무관한 충돌은 그대로 전파
        existing = await reports_repo.find_report_by_idempotency_key(
            session, idempotency_key
        )
        if existing is None:
            # 매우 드문 경계 — IntegrityError가 다른 unique 충돌이었던 경우.
            raise
        return ReportCreateResponse(report_id=existing.id, status=existing.status)

    try:
        await temporal.start_workflow(
            ReportTriageWorkflow.run,
            report_id,
            id=f"report-triage-{report_id}",
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
    except Exception as err:  # pragma: no cover - Temporal 장애 시 운영자가 재시도
        # 신고는 이미 저장됐으므로 클라이언트가 report_id를 알아야
        # POST /reports/{report_id}/reprocess로 복구할 수 있다.
        # (FR-1: 저장 성공/실패와 workflow 시작을 분리해서 다룬다.)
        # status를 명시적인 sentinel로 바꿔 두면 GET /reports/{id}만 봐도
        # "workflow가 시작조차 못 했다"를 운영자가 구분할 수 있다.
        logger.exception("failed to start triage workflow for %s", report_id)
        try:
            await reports_repo.update_report_status(
                session, report_id, ReportStatus.WORKFLOW_START_FAILED
            )
            await session.commit()
        except Exception:
            logger.exception("failed to mark workflow_start_failed for %s", report_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "report_id": report_id,
                "status": ReportStatus.WORKFLOW_START_FAILED.value,
                "error": "workflow start failed",
                "message": (
                    "report saved but triage workflow could not be started; "
                    "retry via POST /reports/{report_id}/reprocess once Temporal recovers"
                ),
                "cause": str(err),
            },
        ) from err

    return ReportCreateResponse(report_id=report_id, status=ReportStatus.QUEUED)


@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(
    report_id: str,
    session: AsyncSession = Depends(get_session),
) -> ReportDetailResponse:
    """DB의 reports.status 기준으로 종단 상태와 분류 결과를 반환한다."""
    report = await reports_repo.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")

    return ReportDetailResponse(
        report_id=report.id,
        status=report.status,
        report=_to_payload(report),
        classification=_to_classification(report),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "/{report_id}/reprocess",
    response_model=ReprocessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_report(
    report_id: str,
    session: AsyncSession = Depends(get_session),
    temporal: Client = Depends(get_temporal_client),
) -> ReprocessResponse:
    """기존 신고를 다시 분류한다.

    - 없는 신고: 404
    - 그 외: status를 `queued`로 되돌리고 안정적인 workflow_id
      `report-triage-{report_id}`로 새 run을 시작한다. 기존 run이 진행 중이면
      Temporal이 `TERMINATE_IF_RUNNING` 정책으로 자동 종료시키므로
      한 시점 active workflow ≤ 1이 보장된다.
    """
    settings = get_settings()
    report = await reports_repo.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")

    await reports_repo.reset_report_for_reprocess(session, report_id)
    await session.commit()

    try:
        await temporal.start_workflow(
            ReportTriageWorkflow.run,
            report_id,
            id=f"report-triage-{report_id}",
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
    except Exception as err:  # pragma: no cover - Temporal 장애 시 운영자가 재시도
        logger.exception("failed to start reprocess workflow for %s", report_id)
        try:
            await reports_repo.update_report_status(
                session, report_id, ReportStatus.WORKFLOW_START_FAILED
            )
            await session.commit()
        except Exception:
            logger.exception("failed to mark workflow_start_failed for %s", report_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"workflow start failed: {err}",
        ) from err

    return ReprocessResponse(report_id=report_id, status=ReportStatus.QUEUED)
