from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from app.temporal import activities

_DEFAULT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=15),
    maximum_attempts=3,
    non_retryable_error_types=["ReportNotFound"],
)

_FAIL_RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn(name="ReportTriageWorkflow")
class ReportTriageWorkflow:
    @workflow.run
    async def run(self, report_id: str) -> dict:
        try:
            report = await workflow.execute_activity(
                activities.load_report_activity,
                report_id,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=_DEFAULT_RETRY,
            )

            await workflow.execute_activity(
                activities.mark_report_processing_activity,
                report_id,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=_DEFAULT_RETRY,
            )

            classification = await workflow.execute_activity(
                activities.classify_report_activity,
                report,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_DEFAULT_RETRY,
            )

            priority_level = await workflow.execute_activity(
                activities.score_priority_activity,
                args=[report, classification["category"]],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=_DEFAULT_RETRY,
            )

            requires_review = await workflow.execute_activity(
                activities.decide_review_activity,
                args=[classification["category"], priority_level, classification["confidence"]],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=_DEFAULT_RETRY,
            )

            queue_name = await workflow.execute_activity(
                activities.persist_classification_activity,
                args=[
                    report_id,
                    classification["category"],
                    priority_level,
                    requires_review,
                    classification["confidence"],
                    classification["reasoning_summary"],
                ],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=_DEFAULT_RETRY,
            )

            await workflow.execute_activity(
                activities.route_queue_activity,
                args=[report_id, queue_name],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=_DEFAULT_RETRY,
            )

            # publish는 best-effort. DB 상태(classification/queue)는 이미 commit 됐고
            # NATS는 "후속 시스템 경계"이므로, publish 실패가 reports.status를 failed로
            # 되돌리는 일은 없어야 한다. 재시도가 다 소진되면 로그만 남기고 계속 진행한다.
            # downstream 카운터가 비는 것은 운영자가 /metrics/events로 관찰 가능하다.
            try:
                await workflow.execute_activity(
                    activities.publish_triage_events_activity,
                    args=[
                        report_id,
                        classification["category"],
                        priority_level,
                        requires_review,
                        classification["confidence"],
                        queue_name,
                    ],
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=_DEFAULT_RETRY,
                )
            except ActivityError:
                workflow.logger.warning(
                    "publish_triage_events failed after retries; "
                    "DB state is already committed, continuing to mark_classified",
                    extra={"report_id": report_id},
                )

            await workflow.execute_activity(
                activities.mark_report_classified_activity,
                report_id,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=_DEFAULT_RETRY,
            )

            return {
                "report_id": report_id,
                "category": classification["category"],
                "priority": priority_level,
                "requires_review": requires_review,
                "queue_name": queue_name,
            }

        except ActivityError as err:
            # 최선 노력: API 조회가 종단 상태를 볼 수 있도록 failed로 기록.
            try:
                await workflow.execute_activity(
                    activities.mark_report_failed_activity,
                    report_id,
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=_FAIL_RETRY,
                )
            except ApplicationError:
                pass
            raise err
