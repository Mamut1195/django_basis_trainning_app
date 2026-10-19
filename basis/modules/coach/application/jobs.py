"""Durable single-call jobs coordinated through explicit locking ports."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol
from uuid import uuid4

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
    CoachInvalid,
    CoachUnavailable,
    Fund,
    Job,
    JobKind,
    ProviderAmbiguous,
    ProviderRejected,
    ProviderReply,
    Usage,
    require_budget,
    usage_cost,
)


@dataclass(frozen=True)
class CoachConfiguration:
    enabled: bool
    credential_configured: bool
    model: str


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
    def prepare(self, kind: JobKind, prompt: str, context: CoachContext, model: str) -> None: ...
    def call(
        self, kind: JobKind, prompt: str, context: CoachContext, model: str
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
        if self.config.model not in ("deepseek-flash", "deepseek-v4-flash") or self.repo.blocked():
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
            reservation = require_budget(command.kind, usage, fund, trial)
            if command.invalid_base_plan:
                raise CoachInvalid("El plan seleccionado no es v\u00e1lido.")
            context = self.contexts.snapshot(command.owner, command.kind, command.base_plan)
            self.provider.prepare(command.kind, command.prompt, context, self.config.model)
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
            )
            self.repo.create(job)
            work.commit()
            return job

    def settle(
        self,
        job_id: JobId,
        data: ProviderReply | None = None,
        error: str = "",
        definitive: bool = False,
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
            if job.status != "running":
                work.commit()
                return job
            if data is None and not definitive:
                job.status, job.error = (
                    "uncertain",
                    "Resultado ambiguo; reserva retenida. No reintentaremos automáticamente.",
                )
                job.completed_at = self.clock.now()
                self.repo.save_job(job)
                work.commit()
                return job
            from decimal import Decimal

            cost = Decimal(0)
            if data is not None:
                try:
                    if data.usage is None:
                        raise CoachInvalid
                    cost = usage_cost(data.usage, job.kind, job.reservation)
                    job.input_tokens = data.usage.input_tokens
                    job.output_tokens = data.usage.output_tokens
                    job.cache_hit_tokens = data.usage.cache_hits
                    job.reported_model = data.reported_model[:100]
                    if not data.choice_present:
                        raise CoachInvalid
                    job.answer = data.answer
                    if not data.answer_is_text or data.finish_reason != "stop":
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

    def process_one(self) -> bool:
        if not self.config.enabled or not self.config.credential_configured or self.repo.blocked():
            return False
        with self.uow() as work:
            job = self.repo.claim(self.clock.now())
            work.commit()
        if job is None:
            return False
        billing = self.billing.get(job.owner)
        if billing is None or not state_entitled(billing, self.clock.now()):
            self.settle(
                job.id,
                error="El acceso activo terminó antes de procesar esta consulta.",
                definitive=True,
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
            )
            return True
        try:
            data = self.provider.call(job.kind, job.prompt, job.context, job.requested_model)
            job = self.settle(job.id, data)
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
            self.settle(job.id, error="El proveedor rechazó la solicitud.", definitive=True)
        except (ProviderAmbiguous, CoachInvalid):
            self.settle(job.id)
        return True

    def quarantine_stale_jobs(self) -> None:
        with self.uow() as work:
            self.repo.quarantine(self.clock.now() - timedelta(minutes=10))
            work.commit()
