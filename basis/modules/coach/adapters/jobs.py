"""Existing durable coach tables behind explicit job repository operations."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast

from django.db import connection

from basis.modules.coach.adapters.models import (
    AIJob,
    AIReconciliation,
    AIServiceState,
    TrialFund,
    UsagePeriod,
)
from basis.shared.identifiers import (
    AccountId,
    AIRequestKey,
    JobId,
    PlanId,
    TrialFundId,
    UsagePeriodId,
)

from ..domain.jobs import (
    CoachInvalid,
    Fund,
    Job,
    JobKind,
    PricingSnapshot,
    Reconcile,
    Reconciliation,
    TokenUsage,
    Usage,
)
from .context_wire import decode_context, encode_context


def encode_pricing(pricing: PricingSnapshot | None) -> dict[str, object] | None:
    if pricing is None:
        return None
    return {
        "version": pricing.version,
        "input_rate": str(pricing.input_rate),
        "hit_rate": str(pricing.hit_rate),
        "output_rate": str(pricing.output_rate),
        "input_limit": pricing.input_limit,
        "output_limit": pricing.output_limit,
        "allowed_models": list(pricing.allowed_models),
    }


def decode_pricing(data: object) -> PricingSnapshot | None:
    if not isinstance(data, dict):
        return None
    try:
        version, inputs, hits, outputs = (
            data[key] for key in ("version", "input_rate", "hit_rate", "output_rate")
        )
        input_limit, output_limit, models = (
            data[key] for key in ("input_limit", "output_limit", "allowed_models")
        )
        if (
            not all(isinstance(value, str) for value in (version, inputs, hits, outputs))
            or type(input_limit) is not int
            or type(output_limit) is not int
            or not isinstance(models, list)
            or any(not isinstance(model, str) for model in models)
        ):
            return None
        pricing = PricingSnapshot(
            version,
            Decimal(inputs),
            Decimal(hits),
            Decimal(outputs),
            input_limit,
            output_limit,
            tuple(models),
        )
        pricing.validate()
        return pricing
    except (KeyError, InvalidOperation, CoachInvalid):
        return None


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
        row.pricing_version,
        decode_pricing(cast(object, row.pricing_snapshot)),
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
            pricing_version=job.pricing_version,
            pricing_snapshot=encode_pricing(job.pricing),
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

    def reconciliation(self, job: JobId, key: str) -> Reconciliation | None:
        row = AIReconciliation.objects.filter(job_id=job, key=key).first()
        if row is None:
            return None
        tokens = cast(dict[str, int] | None, row.token_usage)
        command = Reconcile(
            job,
            row.key,
            row.actor,
            row.reference,
            row.evidence,
            cast("Literal['no_charge', 'usage']", row.decision),
            row.confirmed_no_charge,
            row.reported_model,
            TokenUsage(**tokens) if tokens is not None else None,
        )
        return Reconciliation(
            command, row.outcome, row.reason, row.cost, row.job_status, row.created_at
        )

    def add_reconciliation(self, record: Reconciliation) -> None:
        command = record.command
        tokens = command.usage
        AIReconciliation.objects.create(
            job_id=command.job_id,
            key=command.key,
            actor=command.actor,
            reference=command.reference,
            evidence=command.evidence,
            decision=command.decision,
            confirmed_no_charge=command.confirmed_no_charge,
            reported_model=command.reported_model,
            token_usage={
                "input_tokens": tokens.input_tokens,
                "output_tokens": tokens.output_tokens,
                "cache_hits": tokens.cache_hits,
            }
            if tokens is not None
            else None,
            outcome=record.outcome,
            reason=record.reason,
            cost=record.cost,
            job_status=record.job_status,
            created_at=record.created_at,
        )
