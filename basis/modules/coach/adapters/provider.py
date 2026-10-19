"""Single-call DeepSeek boundary, with injectable transport and no retry path."""

import json
from typing import Protocol

import httpx

from ..domain.context import CoachContext
from ..domain.jobs import (
    LIMITS,
    CoachInvalid,
    JobKind,
    ProviderAmbiguous,
    ProviderRejected,
    ProviderReply,
    TokenUsage,
)
from ..domain.prompts import PLAN_FORMAT, SYSTEM
from .context_wire import encode_context, mapping, rows


class ClientFactory(Protocol):
    def __call__(self, *, timeout: httpx.Timeout) -> httpx.Client: ...


def request_body(
    kind: JobKind, prompt: str, context: CoachContext, model: str
) -> dict[str, object]:
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
        "max_tokens": LIMITS[kind][1],
        "stream": False,
    }
    if kind == "plan":
        body["response_format"] = {"type": "json_object"}
    if len(json.dumps(body, ensure_ascii=False).encode()) + 128 > LIMITS[kind][0]:
        raise CoachInvalid(
            "El contexto supera el presupuesto. Reduce la consulta o completa un objetivo m\u00e1s concreto."
        )
    return body


def decode_reply(value: object) -> ProviderReply | None:
    if not value:
        return None
    if not isinstance(value, dict):
        # Legacy unexpected top-level JSON escapes the worker, leaving its running
        # reservation for stale quarantine; do not silently change retry/accounting.
        raise AttributeError(f"'{type(value).__name__}' object has no attribute 'get'")
    try:
        d = mapping(value)
        counts = mapping(d.get("usage", {}))
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
        return ProviderReply(None)
    reported = str(d.get("model", "unknown"))[:100]
    try:
        choice = mapping(rows(d["choices"])[0])
        answer = mapping(choice["message"])["content"]
        finish = choice.get("finish_reason")
        return ProviderReply(
            usage,
            reported,
            True,
            None if answer is None else str(answer),
            isinstance(answer, str),
            finish if isinstance(finish, str) else None,
        )
    except (ValueError, KeyError, IndexError):
        return ProviderReply(usage, reported)


class DeepSeekProvider:
    def __init__(self, credential: str, client_factory: ClientFactory = httpx.Client) -> None:
        self.credential, self.client_factory = credential, client_factory

    def prepare(self, kind: JobKind, prompt: str, context: CoachContext, model: str) -> None:
        request_body(kind, prompt, context, model)

    def call(
        self, kind: JobKind, prompt: str, context: CoachContext, model: str
    ) -> ProviderReply | None:
        try:
            body = request_body(kind, prompt, context, model)
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
