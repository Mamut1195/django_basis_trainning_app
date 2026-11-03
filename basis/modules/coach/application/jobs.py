"""Durable single-call jobs coordinated through explicit locking ports."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Protocol
from uuid import UUID, uuid4

from basis.modules.accounts.public import AccountLocks
from basis.modules.athletes.public import BillingProfiles
from basis.modules.billing.public import CoachBilling, state_entitled
from basis.shared.identifiers import (
    AccountId,
    AIRequestKey,
    JobId,
    PlanId,
    TrialFundId,
    UsagePeriodId,
)
from basis.shared.ports import Clock, UnitOfWork

from ..domain.context import CoachContext
from ..domain.jobs import (
    HISTORICAL_PRICING,
    CancellationConflict,
    CoachInvalid,
    CoachUnavailable,
    Fund,
    Job,
    JobKind,
    JobNotFound,
    PricingPolicy,
    PricingSnapshot,
    ProviderAmbiguous,
    ProviderRejected,
    ProviderReply,
    Reconcile,
    Reconciliation,
    TokenUsage,
    Usage,
    job_pricing,
    require_budget,
    require_cancellation,
    require_release,
    usage_cost,
)


@dataclass(frozen=True)
class CoachConfiguration:
    enabled: bool
    credential_configured: bool
    model: str
    pricing: PricingPolicy = HISTORICAL_PRICING


@dataclass(frozen=True)
class Enqueue:
    owner: AccountId
    kind: JobKind
    prompt: str
    request_key: AIRequestKey
    base_plan: PlanId | None = None
    invalid_base_plan: bool = False
    base_plan_key: str | None = None


class Contexts(Protocol):
    def snapshot(
        self, owner: AccountId, kind: JobKind, base_plan_id: PlanId | None
    ) -> CoachContext: ...


class Provider(Protocol):
    def prepare(
        self,
        kind: JobKind,
        prompt: str,
        context: CoachContext,
        model: str,
        pricing: PricingSnapshot,
    ) -> None: ...
    def call(
        self,
        kind: JobKind,
        prompt: str,
        context: CoachContext,
        model: str,
        pricing: PricingSnapshot,
    ) -> ProviderReply | None: ...


class ProposalSink(Protocol):
    def complete(self, job: Job) -> bool: ...


class JobsRepository(Protocol):
    def blocked(self) -> bool: ...
    def block(self) -> None: ...
    def lock_month(self, month: str) -> Fund: ...
    def lock_fund(self, fund: TrialFundId) -> Fund: ...
    def fund(self, fund: TrialFundId) -> Fund: ...
    def save_fund(self, fund: Fund) -> None: ...
    def existing(self, owner: AccountId, key: AIRequestKey) -> Job | None: ...
    def lock_period(self, owner: AccountId, key: str, trial: bool) -> Usage: ...
    def lock_usage(self, usage: UsagePeriodId) -> Usage: ...
    def usage(self, usage: UsagePeriodId) -> Usage: ...
    def save_usage(self, usage: Usage) -> None: ...
    def job(self, job: JobId) -> Job: ...
    def lock_job(self, job: JobId) -> Job: ...
    def create(self, job: Job) -> None: ...
    def save_job(self, job: Job) -> None: ...
    def claim(self, now: datetime) -> Job | None: ...
    def quarantine(self, before: datetime) -> None: ...
    def reconciliation(self, job: JobId, key: str) -> Reconciliation | None: ...
    def add_reconciliation(self, record: Reconciliation) -> None: ...


class Jobs:
    def __init__(
        self,
        repo: JobsRepository,
        accounts: AccountLocks,
        billing: CoachBilling,
        profiles: BillingProfiles,
        contexts: Contexts,
        provider: Provider,
        proposals: ProposalSink,
        clock: Clock,
        uow: Callable[[], UnitOfWork],
        config: CoachConfiguration,
    ) -> None:
        self.repo, self.accounts, self.billing = repo, accounts, billing
        self.profiles, self.contexts, self.provider = profiles, contexts, provider
        self.proposals, self.clock, self.uow, self.config = proposals, clock, uow, config

    def require_available(self) -> None:
        if not self.config.enabled or not self.config.credential_configured:
            raise CoachUnavailable("El entrenador IA todavía no está habilitado.")
        if self.config.model not in self.config.pricing.allowed_models or self.repo.blocked():
            raise CoachUnavailable("La IA está pausada hasta verificar modelo, precios y uso.")

    def enqueue(self, command: Enqueue) -> Job:
        with self.uow() as work:
            self.require_available()
            if (
                command.kind not in ("short", "plan")
                or not 1 <= len(command.prompt.strip()) <= 2000
            ):
                raise CoachInvalid("Consulta inválida.")
            fund = self.repo.lock_month(self.clock.now().strftime("%Y-%m"))
            self.accounts.lock(command.owner)
            existing = self.repo.existing(command.owner, command.request_key)
            if existing is not None:
                if (
                    existing.prompt != command.prompt
                    or existing.kind != command.kind
                    or str(existing.base_plan or "")
                    != (
                        command.base_plan_key
                        if command.base_plan_key is not None
                        else str(command.base_plan or "")
                    )
                ):
                    raise CoachInvalid("La petición ya existe con otro contenido.")
                work.commit()
                return existing
            billing = self.billing.lock(command.owner)
            profile = self.profiles.get(command.owner)
            if (
                billing is None
                or not state_entitled(billing, self.clock.now())
                or not billing.customer_id
                or profile is None
                or not profile.email_verified
            ):
                raise CoachInvalid("La IA requiere una prueba o suscripción verificada en Polar.")
            trial = billing.status == "trialing"
            assert billing.period_start is not None
            key = "trial-lifetime" if trial else billing.period_start.isoformat()
            usage = self.repo.lock_period(command.owner, key, trial)
            pricing = self.config.pricing.freeze(command.kind)
            reservation = require_budget(command.kind, usage, fund, trial, pricing)
            if command.invalid_base_plan:
                raise CoachInvalid("El plan seleccionado no es v\u00e1lido.")
            context = self.contexts.snapshot(command.owner, command.kind, command.base_plan)
            self.provider.prepare(command.kind, command.prompt, context, self.config.model, pricing)
            usage.reserved += reservation
            if command.kind == "short":
                usage.short_count += 1
            else:
                usage.plan_count += 1
            self.repo.save_usage(usage)
            if trial:
                fund.reserved += reservation
                self.repo.save_fund(fund)
            job = Job(
                JobId(uuid4()),
                command.owner,
                command.request_key,
                command.kind,
                command.prompt,
                context,
                usage.id,
                fund.id if trial else None,
                reservation,
                self.config.model,
                command.base_plan,
                pricing_version=pricing.version,
                pricing=pricing,
                invalid_usage_observed=False,
            )
            self.repo.create(job)
            work.commit()
            return job

    def cancel(self, owner: AccountId, job_id: JobId) -> Job:
        with self.uow() as work:
            original = self.repo.job(job_id)
            if original.owner != owner:
                raise JobNotFound
            fund = (
                self.repo.lock_fund(original.trial_fund)
                if original.trial_fund is not None
                else None
            )
            self.accounts.lock(owner)
            job = self.repo.lock_job(job_id)
            if job.owner != owner:
                raise JobNotFound
            if job.attempt_id is not None:
                raise CancellationConflict("La consulta ya comenzó; su reserva se conserva.")
            if job.status == "cancelled":
                work.commit()
                return job
            if job.status != "pending":
                raise CancellationConflict(
                    "La consulta ya no está pendiente y no se puede cancelar."
                )
            if (job.trial_fund, job.usage_period) != (
                original.trial_fund,
                original.usage_period,
            ):
                raise CoachInvalid("Cambió el origen de la reserva; reserva retenida.")
            usage = self.repo.lock_usage(job.usage_period)
            require_cancellation(job, usage, fund)
            usage.reserved -= job.reservation
            if job.kind == "short":
                usage.short_count -= 1
            else:
                usage.plan_count -= 1
            self.repo.save_usage(usage)
            if fund is not None:
                fund.reserved -= job.reservation
                self.repo.save_fund(fund)
            job.status, job.cost, job.completed_at = "cancelled", Decimal(0), self.clock.now()
            self.repo.save_job(job)
            work.commit()
            return job

    def settle(
        self,
        job_id: JobId,
        data: ProviderReply | None = None,
        error: str = "",
        definitive: bool = False,
        *,
        attempt_id: UUID | None = None,
    ) -> Job:
        with self.uow() as work:
            original = self.repo.job(job_id)
            fund = (
                self.repo.lock_fund(original.trial_fund)
                if original.trial_fund is not None
                else None
            )
            self.accounts.lock(original.owner)
            job = self.repo.lock_job(job_id)
            usage = self.repo.lock_usage(job.usage_period)
            if (job.attempt_id is not None or attempt_id is not None) and (
                job.attempt_id != attempt_id
            ):
                work.commit()
                return job
            late = job.status == "uncertain" and attempt_id is not None
            if job.status != "running" and not late:
                work.commit()
                return job
            if attempt_id is not None:
                job.attempt_id = None
            if data is None and not definitive:
                job.status, job.error = (
                    "uncertain",
                    "Resultado ambiguo; reserva retenida. No reintentaremos automáticamente.",
                )
                job.completed_at = self.clock.now()
                self.repo.save_job(job)
                work.commit()
                return job
            cost = Decimal(0)
            if data is not None:
                # Keep bounded observations even when validation fails; never infer cost.
                job.reported_model = data.reported_model[:100]
                if data.invalid_usage_observed:
                    job.invalid_usage_observed = True
                if data.usage is not None:
                    # Integer columns cannot represent every provider observation.
                    # Preserve a sticky rejection marker before projecting safe values.
                    job.invalid_usage_observed = job.invalid_usage_observed is True or any(
                        type(value) is not int or not 0 <= value <= 2147483647
                        for value in (
                            data.usage.input_tokens,
                            data.usage.output_tokens,
                            data.usage.cache_hits,
                        )
                    )
                    job.input_tokens, job.output_tokens, job.cache_hit_tokens = (
                        value if type(value) is int and 0 <= value <= 2147483647 else None
                        for value in (
                            data.usage.input_tokens,
                            data.usage.output_tokens,
                            data.usage.cache_hits,
                        )
                    )
                try:
                    pricing = job_pricing(job)
                    if data.reported_model not in pricing.allowed_models:
                        raise CoachInvalid
                    if data.usage is None or data.invalid_usage_observed:
                        raise CoachInvalid
                    try:
                        cost = usage_cost(data.usage, job.kind, job.reservation, pricing)
                    except CoachInvalid:
                        job.invalid_usage_observed = True
                        raise
                    if not data.choice_present:
                        raise CoachInvalid
                    job.answer = data.answer if isinstance(data.answer, str) else ""
                    if (
                        not data.answer_is_text
                        or not isinstance(data.answer, str)
                        or data.finish_reason != "stop"
                    ):
                        error = "La respuesta no terminó correctamente; no se puede aplicar."
                except CoachInvalid:
                    self.repo.block()
                    job.status, job.error = (
                        "uncertain",
                        "Uso o respuesta inesperados. Reserva retenida para conciliación.",
                    )
                    job.completed_at = self.clock.now()
                    self.repo.save_job(job)
                    work.commit()
                    return job
            if late:
                # A quarantined return is evidence, not an automatic settlement.
                self.repo.save_job(job)
                work.commit()
                return job
            try:
                require_release(job, usage, fund, cost)
            except CoachInvalid:
                self.repo.block()
                job.status, job.error = "uncertain", "Saldos incompatibles; reserva retenida."
                job.completed_at = self.clock.now()
                self.repo.save_job(job)
                work.commit()
                return job
            usage.reserved -= job.reservation
            usage.spent += cost
            self.repo.save_usage(usage)
            if fund is not None:
                fund.reserved -= job.reservation
                fund.spent += cost
                self.repo.save_fund(fund)
            job.cost = cost
            job.status, job.error = ("failed", error) if error else ("succeeded", "")
            job.completed_at = self.clock.now()
            self.repo.save_job(job)
            work.commit()
            return job

    def reconcile(self, command: Reconcile, *, apply: bool = False) -> Reconciliation:
        """Administrative evidence only: never calls provider, billing or proposal ports."""
        command.validate()
        with self.uow() as work:
            original = self.repo.job(command.job_id)
            # Same lock order as settlement/enqueue, including the original trial month.
            fund = self.repo.lock_fund(original.trial_fund) if original.trial_fund else None
            self.accounts.lock(original.owner)
            job = self.repo.lock_job(command.job_id)
            usage = self.repo.lock_usage(job.usage_period)
            previous = self.repo.reconciliation(job.id, command.key)
            if previous is not None:
                if previous.command != command:
                    raise CoachInvalid("La clave de conciliación ya tiene otra decisión.")
                return previous
            cost: Decimal | None = None
            reason = ""
            try:
                if job.status != "uncertain":
                    raise CoachInvalid("El job ya no está uncertain; no se ajustan saldos.")
                if job.attempt_id is not None:
                    raise CoachInvalid("Intento abierto; reserva retenida hasta su cierre seguro.")
                if job.invalid_usage_observed is True:
                    raise CoachInvalid(
                        "Uso inválido recibido; la evidencia y reserva permanecen retenidas."
                    )
                if command.decision == "usage":
                    pricing = job_pricing(job)
                    if command.reported_model not in pricing.allowed_models or (
                        job.reported_model
                        and job.reported_model != command.reported_model
                        and job.reported_model not in pricing.allowed_models
                    ):
                        raise CoachInvalid("Modelo discrepante; requiere revisión de política.")
                    assert command.usage is not None
                    cost = usage_cost(command.usage, job.kind, job.reservation, pricing)
                    observed = (job.input_tokens, job.output_tokens, job.cache_hit_tokens)
                    proposed = (
                        command.usage.input_tokens,
                        command.usage.output_tokens,
                        command.usage.cache_hits,
                    )
                    if any(old is not None and old != new for old, new in zip(observed, proposed)):
                        raise CoachInvalid("El uso no coincide con la evidencia del job.")
                else:
                    # Explicit no-charge evidence may resolve missing usage/snapshot, but
                    # known out-of-policy observations still require separate review.
                    if (
                        job.reported_model
                        or job.input_tokens is not None
                        or job.output_tokens is not None
                        or job.cache_hit_tokens is not None
                    ):
                        pricing = job_pricing(job)
                        if job.reported_model and job.reported_model not in pricing.allowed_models:
                            raise CoachInvalid("Modelo discrepante; reserva retenida.")
                        if any(
                            value is not None and (value < 0 or value > limit)
                            for value, limit in (
                                (job.input_tokens, pricing.input_limit),
                                (job.output_tokens, pricing.output_limit),
                                (job.cache_hit_tokens, pricing.input_limit),
                            )
                        ) or (
                            job.cache_hit_tokens is not None
                            and job.input_tokens is not None
                            and job.cache_hit_tokens > job.input_tokens
                        ):
                            raise CoachInvalid("Uso observado fuera de límites; reserva retenida.")
                        if job.input_tokens is not None and job.output_tokens is not None:
                            usage_cost(
                                TokenUsage(
                                    job.input_tokens, job.output_tokens, job.cache_hit_tokens or 0
                                ),
                                job.kind,
                                job.reservation,
                                pricing,
                            )
                    cost = Decimal(0)
                require_release(job, usage, fund, cost)
            except CoachInvalid as exc:
                cost = None
                reason = str(exc) or "Uso fuera de límites; reserva retenida."
            outcome = (
                "retained"
                if cost is None
                else ("released" if command.decision == "no_charge" else "charged")
            )
            if cost is not None:
                usage.reserved -= job.reservation
                usage.spent += cost
                self.repo.save_usage(usage)
                if fund is not None:
                    fund.reserved -= job.reservation
                    fund.spent += cost
                    self.repo.save_fund(fund)
                job.cost, job.status = cost, "failed"
                job.error = "Conciliado administrativamente; no se aplica respuesta ni se reenvía."
                job.completed_at = self.clock.now()
                self.repo.save_job(job)
            record = Reconciliation(command, outcome, reason, cost, job.status, self.clock.now())
            self.repo.add_reconciliation(record)
            if apply:
                work.commit()
            return record

    def process_one(self) -> bool:
        if not self.config.enabled or not self.config.credential_configured or self.repo.blocked():
            return False
        with self.uow() as work:
            job = self.repo.claim(self.clock.now())
            work.commit()
        if job is None:
            return False
        try:
            pricing = job_pricing(job)
        except CoachInvalid:
            # An unverifiable pending policy must never reach the provider.
            self.settle(job.id, attempt_id=job.attempt_id)
            with self.uow() as work:
                self.repo.block()
                work.commit()
            return True
        billing = self.billing.get(job.owner)
        if billing is None or not state_entitled(billing, self.clock.now()):
            self.settle(
                job.id,
                error="El acceso activo terminó antes de procesar esta consulta.",
                definitive=True,
                attempt_id=job.attempt_id,
            )
            return True
        usage = self.repo.usage(job.usage_period)
        trial_now = billing.status == "trialing"
        assert billing.period_start is not None
        if (
            usage.is_trial != trial_now
            or (not trial_now and usage.key != billing.period_start.isoformat())
            or (
                job.trial_fund is not None
                and self.repo.fund(job.trial_fund).month != self.clock.now().strftime("%Y-%m")
            )
        ):
            self.settle(
                job.id,
                error="El período cambió antes de procesar la consulta. Solicita una nueva revisión.",
                definitive=True,
                attempt_id=job.attempt_id,
            )
            return True
        try:
            data = self.provider.call(
                job.kind, job.prompt, job.context, job.requested_model, pricing
            )
            job = self.settle(job.id, data, attempt_id=job.attempt_id)
            if (
                job.status == "succeeded"
                and job.kind == "plan"
                and not self.proposals.complete(job)
            ):
                with self.uow() as work:
                    job.status = "failed"
                    job.error = "La propuesta no supera la validación deportiva. No se aplicó ningún cambio."
                    self.repo.save_job(job)
                    work.commit()
        except ProviderRejected:
            self.settle(
                job.id,
                error="El proveedor rechazó la solicitud.",
                definitive=True,
                attempt_id=job.attempt_id,
            )
        except (ProviderAmbiguous, CoachInvalid):
            self.settle(job.id, attempt_id=job.attempt_id)
        return True

    def quarantine_stale_jobs(self) -> None:
        with self.uow() as work:
            self.repo.quarantine(self.clock.now() - timedelta(minutes=10))
            work.commit()
