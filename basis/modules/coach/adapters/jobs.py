"""Existing durable coach tables behind explicit job repository operations."""

from datetime import datetime
from typing import cast

from django.db import connection

from basis.modules.coach.adapters.models import AIJob, AIServiceState, TrialFund, UsagePeriod
from basis.shared.identifiers import (
    AccountId,
    AIRequestKey,
    JobId,
    PlanId,
    TrialFundId,
    UsagePeriodId,
)

from ..domain.jobs import Fund, Job, JobKind, Usage
from .context_wire import decode_context, encode_context


def job_state(row: AIJob) -> Job:
    return Job(
        JobId(row.pk),
        AccountId(row.owner_id),
        AIRequestKey(row.request_key),
        cast(JobKind, row.kind),
        row.prompt,
        decode_context(cast(object, row.context)),
        UsagePeriodId(row.usage_period_id),
        TrialFundId(row.trial_fund_id) if row.trial_fund_id is not None else None,
        row.reservation,
        row.requested_model,
        PlanId(row.base_plan_id) if row.base_plan_id is not None else None,
        row.status,
        row.cost,
        row.reported_model,
        row.input_tokens,
        row.output_tokens,
        row.cache_hit_tokens,
        row.answer,
        row.error,
        row.started_at,
        row.completed_at,
    )


def usage_state(row: UsagePeriod) -> Usage:
    return Usage(
        UsagePeriodId(row.pk),
        AccountId(row.owner_id),
        row.key,
        row.is_trial,
        row.spent,
        row.reserved,
        row.short_count,
        row.plan_count,
    )


def fund_state(row: TrialFund) -> Fund:
    return Fund(TrialFundId(row.pk), row.month, row.spent, row.reserved, row.cap)


class DjangoJobsRepository:
    def blocked(self) -> bool:
        return AIServiceState.objects.filter(blocked=True).exists()

    def block(self) -> None:
        AIServiceState.objects.update_or_create(
            key="deepseek",
            defaults={
                "blocked": True,
                "reason": "Uso de tokens o formato inesperado; conciliar antes de reactivar.",
            },
        )

    def lock_month(self, month: str) -> Fund:
        TrialFund.objects.get_or_create(month=month)
        return fund_state(TrialFund.objects.select_for_update().get(month=month))

    def lock_fund(self, fund: TrialFundId) -> Fund:
        return fund_state(TrialFund.objects.select_for_update().get(pk=fund))

    def fund(self, fund: TrialFundId) -> Fund:
        return fund_state(TrialFund.objects.get(pk=fund))

    def save_fund(self, fund: Fund) -> None:
        TrialFund.objects.filter(pk=fund.id).update(spent=fund.spent, reserved=fund.reserved)

    def existing(self, owner: AccountId, key: AIRequestKey) -> Job | None:
        row = AIJob.objects.filter(owner_id=owner, request_key=key).first()
        return job_state(row) if row is not None else None

    def lock_period(self, owner: AccountId, key: str, trial: bool) -> Usage:
        row, _ = UsagePeriod.objects.get_or_create(
            owner_id=owner, key=key, defaults={"is_trial": trial}
        )
        return usage_state(UsagePeriod.objects.select_for_update().get(pk=row.pk))

    def lock_usage(self, usage: UsagePeriodId) -> Usage:
        return usage_state(UsagePeriod.objects.select_for_update().get(pk=usage))

    def usage(self, usage: UsagePeriodId) -> Usage:
        return usage_state(UsagePeriod.objects.get(pk=usage))

    def save_usage(self, usage: Usage) -> None:
        UsagePeriod.objects.filter(pk=usage.id).update(
            spent=usage.spent,
            reserved=usage.reserved,
            short_count=usage.short_count,
            plan_count=usage.plan_count,
        )

    def job(self, job: JobId) -> Job:
        return job_state(AIJob.objects.get(pk=job))

    def lock_job(self, job: JobId) -> Job:
        return job_state(AIJob.objects.select_for_update().get(pk=job))

    def create(self, job: Job) -> None:
        AIJob.objects.create(
            id=job.id,
            owner_id=job.owner,
            request_key=job.request_key,
            kind=job.kind,
            prompt=job.prompt,
            context=encode_context(job.context),
            usage_period_id=job.usage_period,
            trial_fund_id=job.trial_fund,
            reservation=job.reservation,
            requested_model=job.requested_model,
            base_plan_id=job.base_plan,
        )

    def save_job(self, job: Job) -> None:
        AIJob.objects.filter(pk=job.id).update(
            status=job.status,
            cost=job.cost,
            reported_model=job.reported_model,
            input_tokens=job.input_tokens,
            output_tokens=job.output_tokens,
            cache_hit_tokens=job.cache_hit_tokens,
            answer=job.answer,
            error=job.error,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    def claim(self, now: datetime) -> Job | None:
        rows = AIJob.objects.filter(status="pending").order_by("created_at")
        rows = (
            rows.select_for_update(skip_locked=True)
            if connection.features.has_select_for_update_skip_locked
            else rows.select_for_update()
        )
        row = rows.first()
        if row is None:
            return None
        AIJob.objects.filter(pk=row.pk).update(status="running", started_at=now)
        row.status, row.started_at = "running", now
        return job_state(row)

    def quarantine(self, before: datetime) -> None:
        AIJob.objects.filter(status="running", started_at__lt=before).update(
            status="uncertain",
            error="El proceso se interrumpió; reserva retenida.",
        )
