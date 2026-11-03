"""Provider-independent job state and conservative budget arithmetic."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from typing import Literal
from uuid import UUID

from basis.shared.identifiers import (
    AccountId,
    AIRequestKey,
    JobId,
    PlanId,
    TrialFundId,
    UsagePeriodId,
)

from .context import CoachContext

JobKind = Literal["short", "plan"]
INPUT_RATE = Decimal("0.30") / 1000000
HIT_RATE = Decimal("0.006") / 1000000
OUTPUT_RATE = Decimal("1.20") / 1000000
LIMITS: dict[str, tuple[int, int]] = {"short": (4000, 1500), "plan": (8000, 3000)}


class CoachInvalid(Exception):
    pass


class CoachUnavailable(Exception):
    pass


class ProviderRejected(Exception):
    pass


class ProviderAmbiguous(Exception):
    pass


@dataclass(frozen=True)
class PricingSnapshot:
    """Local accounting policy, not a claim about a provider's live prices."""

    version: str
    input_rate: Decimal
    hit_rate: Decimal
    output_rate: Decimal
    input_limit: int
    output_limit: int
    allowed_models: tuple[str, ...]

    def validate(self) -> None:
        rates = (self.input_rate, self.hit_rate, self.output_rate)
        if (
            not self.version.strip()
            or len(self.version) > 30
            or any(not rate.is_finite() or rate < 0 for rate in rates)
            or any(
                rate != 0 and not Decimal("1e-18") <= rate <= Decimal("9999.99999999")
                for rate in rates
            )
            or self.hit_rate > self.input_rate
            or any(
                type(n) is not int or not 0 < n <= 2147483647
                for n in (self.input_limit, self.output_limit)
            )
            or not self.allowed_models
            or any(not model.strip() or len(model) > 100 for model in self.allowed_models)
        ):
            raise CoachInvalid("Política de costo no verificable.")


@dataclass(frozen=True)
class PricingPolicy:
    version: str = "flash-peak-2026-10-17"
    input_rate: Decimal = INPUT_RATE
    hit_rate: Decimal = HIT_RATE
    output_rate: Decimal = OUTPUT_RATE
    short_limits: tuple[int, int] = (4000, 1500)
    plan_limits: tuple[int, int] = (8000, 3000)
    allowed_models: tuple[str, ...] = ("deepseek-flash", "deepseek-v4-flash")

    def freeze(self, kind: JobKind) -> PricingSnapshot:
        inputs, outputs = self.short_limits if kind == "short" else self.plan_limits
        snapshot = PricingSnapshot(
            self.version,
            self.input_rate,
            self.hit_rate,
            self.output_rate,
            inputs,
            outputs,
            self.allowed_models,
        )
        snapshot.validate()
        return snapshot


HISTORICAL_PRICING = PricingPolicy()


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cache_hits: int = 0


@dataclass(frozen=True)
class ProviderReply:
    usage: TokenUsage | None
    reported_model: str = "unknown"
    choice_present: bool = False
    answer: str | None = ""
    answer_is_text: bool = True
    finish_reason: str | None = None
    invalid_usage_observed: bool = False


@dataclass
class Usage:
    id: UsagePeriodId
    owner: AccountId
    key: str
    is_trial: bool
    spent: Decimal = Decimal(0)
    reserved: Decimal = Decimal(0)
    short_count: int = 0
    plan_count: int = 0


@dataclass
class Fund:
    id: TrialFundId
    month: str
    spent: Decimal = Decimal(0)
    reserved: Decimal = Decimal(0)
    cap: Decimal = Decimal(5)


@dataclass
class Job:
    id: JobId
    owner: AccountId
    request_key: AIRequestKey
    kind: JobKind
    prompt: str
    context: CoachContext
    usage_period: UsagePeriodId
    trial_fund: TrialFundId | None
    reservation: Decimal
    requested_model: str
    base_plan: PlanId | None = None
    status: str = "pending"
    cost: Decimal | None = None
    reported_model: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_hit_tokens: int | None = None
    answer: str = ""
    error: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    pricing_version: str = "flash-peak-2026-10-17"
    pricing: PricingSnapshot | None = None
    invalid_usage_observed: bool | None = None
    attempt_id: UUID | None = None


def job_pricing(job: Job) -> PricingSnapshot:
    snapshot = job.pricing
    if snapshot is None or snapshot.version != job.pricing_version:
        raise CoachInvalid("Falta una tarifa congelada verificable.")
    snapshot.validate()
    if job.requested_model not in snapshot.allowed_models or job.reservation != reservation_for(
        job.kind, snapshot
    ):
        raise CoachInvalid("La reserva no corresponde a su política congelada.")
    return snapshot


@dataclass(frozen=True)
class Reconcile:
    job_id: JobId
    key: str
    actor: str
    reference: str
    evidence: str
    decision: Literal["no_charge", "usage"]
    confirmed_no_charge: bool = False
    reported_model: str = ""
    usage: TokenUsage | None = None

    def validate(self) -> None:
        if any(
            not value.strip() or len(value) > limit
            for value, limit in (
                (self.key, 100),
                (self.actor, 150),
                (self.reference, 500),
                (self.evidence, 4000),
            )
        ) or self.decision not in ("no_charge", "usage"):
            raise CoachInvalid("Se requieren clave, actor, referencia y evidencia explícitos.")
        if self.decision == "no_charge" and (
            not self.confirmed_no_charge or self.usage is not None or self.reported_model
        ):
            raise CoachInvalid("No-cobro requiere confirmación explícita y sin uso imputado.")
        if self.decision == "usage" and (self.confirmed_no_charge or self.usage is None):
            raise CoachInvalid("La decisión de uso requiere tokens y modelo verificados.")


@dataclass(frozen=True)
class Reconciliation:
    command: Reconcile
    outcome: str
    reason: str
    cost: Decimal | None
    job_status: str
    created_at: datetime


def reservation_for(kind: JobKind, pricing: PricingSnapshot | None = None) -> Decimal:
    pricing = pricing or HISTORICAL_PRICING.freeze(kind)
    pricing.validate()
    return (
        pricing.input_limit * pricing.input_rate + pricing.output_limit * pricing.output_rate
    ).quantize(Decimal("0.00000001"), rounding=ROUND_CEILING)


def require_budget(
    kind: JobKind,
    usage: Usage,
    fund: Fund,
    trial: bool,
    pricing: PricingSnapshot | None = None,
) -> Decimal:
    cap, short_cap, plan_cap = (Decimal("0.03"), 5, 1) if trial else (Decimal("1.00"), 200, 8)
    if (kind == "short" and usage.short_count >= short_cap) or (
        kind == "plan" and usage.plan_count >= plan_cap
    ):
        raise CoachInvalid("Has usado las acciones IA disponibles en este período.")
    reservation = reservation_for(kind, pricing)
    if usage.spent + usage.reserved + reservation > cap:
        raise CoachInvalid("Se alcanzó el presupuesto IA de este período.")
    if trial and fund.spent + fund.reserved + reservation > fund.cap:
        raise CoachInvalid(
            "El fondo mensual de IA para pruebas se agotó. Tu registro manual sigue disponible."
        )
    return reservation


def usage_cost(
    usage: TokenUsage,
    kind: JobKind,
    reservation: Decimal,
    pricing: PricingSnapshot | None = None,
) -> Decimal:
    pricing = pricing or HISTORICAL_PRICING.freeze(kind)
    pricing.validate()
    values = (usage.input_tokens, usage.output_tokens, usage.cache_hits)
    if (
        any(type(n) is not int or n < 0 for n in values)
        or usage.cache_hits > usage.input_tokens
        or usage.input_tokens > pricing.input_limit
        or usage.output_tokens > pricing.output_limit
    ):
        raise CoachInvalid
    cost = (
        (usage.input_tokens - usage.cache_hits) * pricing.input_rate
        + usage.cache_hits * pricing.hit_rate
        + usage.output_tokens * pricing.output_rate
    ).quantize(Decimal("0.00000001"), rounding=ROUND_CEILING)
    if cost > reservation:
        raise CoachInvalid
    return cost


def require_release(job: Job, usage: Usage, fund: Fund | None, cost: Decimal) -> None:
    """Refuse corrupt/overdrawn aggregates rather than clamp or release twice."""
    cap = Decimal("0.03") if usage.is_trial else Decimal("1")
    if (
        job.cost is not None
        or job.invalid_usage_observed is True
        or job.reservation < 0
        or cost < 0
        or cost > job.reservation
        or usage.owner != job.owner
        or usage.id != job.usage_period
        or usage.is_trial != (fund is not None)
        or usage.reserved < job.reservation
        or usage.spent < 0
        or usage.spent + usage.reserved > cap
        or (
            fund is not None
            and (
                fund.id != job.trial_fund
                or fund.reserved < job.reservation
                or fund.spent < 0
                or fund.spent + fund.reserved > fund.cap
            )
        )
    ):
        raise CoachInvalid("Saldos incompatibles; reserva retenida.")
