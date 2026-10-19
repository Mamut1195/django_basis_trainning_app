"""Provider-independent job state and conservative budget arithmetic."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from typing import Literal

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
    answer: str | None = ""
    error: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


def reservation_for(kind: JobKind) -> Decimal:
    inputs, outputs = LIMITS[kind]
    return inputs * INPUT_RATE + outputs * OUTPUT_RATE


def require_budget(kind: JobKind, usage: Usage, fund: Fund, trial: bool) -> Decimal:
    cap, short_cap, plan_cap = (Decimal("0.03"), 5, 1) if trial else (Decimal("1.00"), 200, 8)
    if (kind == "short" and usage.short_count >= short_cap) or (
        kind == "plan" and usage.plan_count >= plan_cap
    ):
        raise CoachInvalid("Has usado las acciones IA disponibles en este período.")
    reservation = reservation_for(kind)
    if usage.spent + usage.reserved + reservation > cap:
        raise CoachInvalid("Se alcanzó el presupuesto IA de este período.")
    if trial and fund.spent + fund.reserved + reservation > fund.cap:
        raise CoachInvalid(
            "El fondo mensual de IA para pruebas se agotó. Tu registro manual sigue disponible."
        )
    return reservation


def usage_cost(usage: TokenUsage, kind: JobKind, reservation: Decimal) -> Decimal:
    values = (usage.input_tokens, usage.output_tokens, usage.cache_hits)
    if any(type(n) is not int or n < 0 for n in values) or usage.cache_hits > usage.input_tokens:
        raise CoachInvalid
    cost = (
        (usage.input_tokens - usage.cache_hits) * INPUT_RATE
        + usage.cache_hits * HIT_RATE
        + usage.output_tokens * OUTPUT_RATE
    ).quantize(Decimal("0.00000001"), rounding=ROUND_CEILING)
    if (
        usage.input_tokens > LIMITS[kind][0]
        or usage.output_tokens > LIMITS[kind][1]
        or cost > reservation
    ):
        raise CoachInvalid
    return cost
