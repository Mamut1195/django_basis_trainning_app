"""Django input actions for the typed durable coach use cases."""

from typing import cast
from uuid import UUID

import httpx
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

from basis.bootstrap.coach import contexts, jobs
from basis.modules.billing.public import ProviderUnavailable
from basis.modules.coach.adapters.context_wire import decode_context, encode_context
from basis.modules.coach.adapters.provider import decode_reply
from basis.modules.coach.adapters.provider import request_body as encode_request
from basis.modules.coach.domain.jobs import (
    HIT_RATE,
    INPUT_RATE,
    LIMITS,
    OUTPUT_RATE,
    CoachInvalid,
    CoachUnavailable,
    JobKind,
)
from basis.modules.coach.domain.prompts import PLAN_FORMAT, SYSTEM
from basis.shared.identifiers import AccountId, AIRequestKey, JobId, PlanId

from .models import AIJob

__all__ = (
    "INPUT_RATE",
    "HIT_RATE",
    "OUTPUT_RATE",
    "LIMITS",
    "SYSTEM",
    "PLAN_FORMAT",
    "context_snapshot",
    "request_body",
    "enqueue",
    "settle",
    "process_one",
    "quarantine_stale_jobs",
)


def context_snapshot(owner: AbstractUser, kind: JobKind = "short") -> dict[str, object]:
    return encode_context(contexts().snapshot(AccountId(owner.pk), kind, None))


def request_body(kind: JobKind, prompt: str, context: object, model: str) -> dict[str, object]:
    try:
        return encode_request(kind, prompt, decode_context(context), model)
    except CoachInvalid as error:
        raise ValidationError(str(error)) from None


def enqueue(
    owner: AbstractUser,
    kind: object,
    prompt: object,
    request_key: object,
    base_plan_id: object = None,
) -> AIJob:
    from basis.modules.coach.application.jobs import Enqueue

    service = jobs(httpx.Client)
    try:
        service.require_available()
        if (
            kind not in LIMITS
            or not isinstance(prompt, str)
            or not 1 <= len(prompt.strip()) <= 2000
        ):
            raise ValidationError("Consulta inv\u00e1lida.")
        try:
            key = AIRequestKey(UUID(str(request_key)))
        except (ValueError, TypeError):
            raise ValidationError("Identificador de petici\u00f3n inv\u00e1lido.") from None
        invalid = False
        try:
            selected = PlanId(int(cast(str | int | float, base_plan_id))) if base_plan_id else None
        except (ValueError, TypeError):
            selected, invalid = None, True
        result = service.enqueue(
            Enqueue(
                AccountId(owner.pk),
                cast(JobKind, kind),
                prompt,
                key,
                selected,
                invalid_base_plan=invalid,
                base_plan_key=str(base_plan_id or ""),
            )
        )
        return AIJob.objects.get(pk=result.id, owner_id=owner.pk)
    except CoachUnavailable as error:
        raise ProviderUnavailable(str(error)) from None
    except CoachInvalid as error:
        raise ValidationError(str(error)) from None


def settle(job_id: UUID, data: object = None, error: str = "", definitive: bool = False) -> AIJob:
    result = jobs(httpx.Client).settle(JobId(job_id), decode_reply(data), error, definitive)
    return AIJob.objects.get(pk=result.id)


def process_one() -> bool:
    return jobs(httpx.Client).process_one()


def quarantine_stale_jobs() -> None:
    jobs(httpx.Client).quarantine_stale_jobs()
