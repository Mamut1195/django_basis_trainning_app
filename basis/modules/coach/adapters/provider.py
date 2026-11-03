"""Single-call DeepSeek boundary, with injectable transport and no retry path."""

import json
from typing import Protocol

import httpx

from ..domain.context import CoachContext
from ..domain.jobs import (
    CoachInvalid,
    JobKind,
    PricingSnapshot,
    ProviderAmbiguous,
    ProviderRejected,
    ProviderReply,
    TokenUsage,
)
from ..domain.prompts import INSTRUCTIONS_VERSION, PLAN_FORMAT, SYSTEM, instructions_digest
from .context_wire import encode_context, mapping, rows


class ClientFactory(Protocol):
    def __call__(self, *, timeout: httpx.Timeout) -> httpx.Client: ...


def request_body(
    kind: JobKind, prompt: str, context: CoachContext, model: str, pricing: PricingSnapshot
) -> dict[str, object]:
    pricing.validate()
    if model not in pricing.allowed_models:
        raise CoachInvalid("El modelo no pertenece a la política congelada.")
    if context.schema_version >= 2 and (
        context.instructions_version != INSTRUCTIONS_VERSION
        or context.system_sha256 != instructions_digest(SYSTEM)
        or (kind == "plan" and context.plan_sha256 != instructions_digest(PLAN_FORMAT))
    ):
        raise CoachInvalid(
            "Las instrucciones cambiaron desde la captura. Solicita una nueva revisión."
        )
    message = json.dumps(
        {"context": encode_context(context), "request": prompt},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    body: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM + ("\n" + PLAN_FORMAT if kind == "plan" else "")},
            {"role": "user", "content": message},
        ],
        "thinking": {"type": "disabled"},
        "max_tokens": pricing.output_limit,
        "stream": False,
    }
    if kind == "plan":
        body["response_format"] = {"type": "json_object"}
    if len(json.dumps(body, ensure_ascii=False).encode()) + 128 > pricing.input_limit:
        raise CoachInvalid(
            "El contexto supera el presupuesto. Reduce la consulta o completa un objetivo m\u00e1s concreto."
        )
    return body


def decode_reply(value: object) -> ProviderReply | None:
    if not value or not isinstance(value, dict):
        # No trustworthy usage: let settlement retain the reservation without retry.
        return None
    try:
        d = mapping(value)
    except ValueError:
        return ProviderReply(None)
    if "usage" not in d:
        return ProviderReply(None)
    try:
        counts = mapping(d["usage"])
        ins, outs, hits = (
            counts["prompt_tokens"],
            counts["completion_tokens"],
            counts.get("prompt_cache_hit_tokens", 0),
        )
        usage = (
            TokenUsage(ins, outs, hits)
            if (type(ins) is int and type(outs) is int and type(hits) is int)
            else None
        )
    except (ValueError, KeyError):
        return ProviderReply(None, invalid_usage_observed=True)
    invalid_usage = usage is None
    reported = str(d.get("model", "unknown"))[:100]
    try:
        choice = mapping(rows(d["choices"])[0])
        answer = mapping(choice["message"])["content"]
        finish = choice.get("finish_reason")
        return ProviderReply(
            usage,
            reported,
            True,
            answer if isinstance(answer, str) else "",
            isinstance(answer, str),
            finish if isinstance(finish, str) else None,
            invalid_usage,
        )
    except (ValueError, KeyError, IndexError):
        return ProviderReply(usage, reported, invalid_usage_observed=invalid_usage)


class DeepSeekProvider:
    def __init__(self, credential: str, client_factory: ClientFactory = httpx.Client) -> None:
        self.credential, self.client_factory = credential, client_factory

    def prepare(
        self,
        kind: JobKind,
        prompt: str,
        context: CoachContext,
        model: str,
        pricing: PricingSnapshot,
    ) -> None:
        request_body(kind, prompt, context, model, pricing)

    def call(
        self,
        kind: JobKind,
        prompt: str,
        context: CoachContext,
        model: str,
        pricing: PricingSnapshot,
    ) -> ProviderReply | None:
        try:
            body = request_body(kind, prompt, context, model, pricing)
            with self.client_factory(timeout=httpx.Timeout(90, connect=10)) as client:
                response = client.post(
                    "https://api.deepseek.com/chat/completions",
                    json=body,
                    headers={"Authorization": "Bearer " + self.credential},
                )
            if response.status_code in (400, 401, 403, 404, 422, 429):
                raise ProviderRejected
            response.raise_for_status()
            return decode_reply(response.json())
        except (httpx.HTTPError, ValueError, CoachInvalid):
            raise ProviderAmbiguous from None
