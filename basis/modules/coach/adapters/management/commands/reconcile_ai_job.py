"""Evidence-based local administration; this command never dispatches a worker."""

import json
from typing import Literal, cast
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError, CommandParser

from basis.bootstrap.coach import jobs
from basis.modules.coach.adapters.jobs import encode_pricing
from basis.modules.coach.domain.jobs import CoachInvalid, Reconcile, TokenUsage
from basis.shared.identifiers import JobId


class Command(BaseCommand):
    help = "Inspect/dry-run an uncertain AI job; require --apply to persist an audited decision."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("job_id", type=UUID)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true")
        mode.add_argument("--dry-run", action="store_true")
        parser.add_argument("--decision", choices=("no_charge", "usage"))
        for field in ("key", "actor", "reference", "evidence", "reported-model"):
            parser.add_argument(f"--{field}", default="")
        parser.add_argument("--confirmed-no-charge", action="store_true")
        for field in ("input-tokens", "output-tokens", "cache-hits"):
            parser.add_argument(f"--{field}", type=int)

    def handle(self, *args: object, **options: object) -> None:
        service = jobs()
        job_id = JobId(cast(UUID, options["job_id"]))
        try:
            if options["decision"] is None:
                if options["apply"]:
                    raise CommandError("--apply requiere una decisión explícita.")
                job = service.repo.job(job_id)
                record = (
                    service.repo.reconciliation(job_id, cast(str, options["key"]))
                    if options["key"]
                    else None
                )
                self.stdout.write(
                    json.dumps(
                        {
                            "mode": "query",
                            "job": str(job.id),
                            "status": job.status,
                            "reservation": str(job.reservation),
                            "cost": format(job.cost, ".8f") if job.cost is not None else None,
                            "pricing_version": job.pricing_version,
                            "pricing": encode_pricing(job.pricing),
                            "reported_model": job.reported_model,
                            "invalid_usage_observed": job.invalid_usage_observed,
                            "service_blocked": service.repo.blocked(),
                            "reconciliation": {
                                "key": record.command.key,
                                "actor": record.command.actor,
                                "reference": record.command.reference,
                                "evidence": record.command.evidence,
                                "decision": record.command.decision,
                                "outcome": record.outcome,
                                "reason": record.reason,
                                "cost": format(record.cost, ".8f")
                                if record.cost is not None
                                else None,
                                "created_at": record.created_at.isoformat(),
                            }
                            if record is not None
                            else None,
                        },
                        ensure_ascii=False,
                    )
                )
                return
            decision = cast("Literal['no_charge', 'usage']", options["decision"])
            inputs, outputs, hits = (
                cast(int | None, options[field])
                for field in ("input_tokens", "output_tokens", "cache_hits")
            )
            if decision == "usage" and any(n is None for n in (inputs, outputs, hits)):
                raise CommandError(
                    "Uso conocido requiere input-tokens, output-tokens y cache-hits."
                )
            if decision == "no_charge" and any(n is not None for n in (inputs, outputs, hits)):
                raise CommandError("No-cobro no admite tokens imputados.")
            tokens = (
                TokenUsage(inputs, outputs, hits)
                if inputs is not None and outputs is not None and hits is not None
                else None
            )
            record = service.reconcile(
                Reconcile(
                    job_id,
                    cast(str, options["key"]),
                    cast(str, options["actor"]),
                    cast(str, options["reference"]),
                    cast(str, options["evidence"]),
                    decision,
                    bool(options["confirmed_no_charge"]),
                    cast(str, options["reported_model"]),
                    tokens,
                ),
                apply=bool(options["apply"]),
            )
            self.stdout.write(
                json.dumps(
                    {
                        "mode": "applied" if options["apply"] else "dry-run",
                        "job": str(job_id),
                        "key": record.command.key,
                        "outcome": record.outcome,
                        "reason": record.reason,
                        "cost": format(record.cost, ".8f") if record.cost is not None else None,
                        "status": record.job_status,
                    },
                    ensure_ascii=False,
                )
            )
        except (CoachInvalid, ObjectDoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
