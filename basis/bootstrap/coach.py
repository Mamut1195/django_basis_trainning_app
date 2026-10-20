"""Explicit coach composition, with legacy transport seam supplied by its caller."""

from collections.abc import Callable

from django.conf import settings

from basis.adapters.django.transactions import DjangoClock, DjangoUnitOfWork
from basis.bootstrap.billing import write_authorization
from basis.bootstrap.planning import planning
from basis.modules.accounts.adapters.coach import DjangoAccountLocks
from basis.modules.athletes.adapters.billing import DjangoBillingProfiles
from basis.modules.athletes.adapters.coach import DjangoAthleteCoachContexts
from basis.modules.billing.adapters.coach import DjangoCoachBilling
from basis.modules.catalog.adapters.coach import DjangoCoachExercises
from basis.modules.coach.adapters.jobs import DjangoJobsRepository
from basis.modules.coach.adapters.proposals import DjangoProposalRepository, DjangoProposalSink
from basis.modules.coach.adapters.provider import ClientFactory, DeepSeekProvider
from basis.modules.coach.application.context import Contexts
from basis.modules.coach.application.jobs import CoachConfiguration, Jobs
from basis.modules.coach.application.proposals import Proposals
from basis.modules.training.adapters.coach import DjangoCoachPlanning, DjangoTrainingCoachContexts
from basis.modules.training.adapters.plan_wire import proposal_definition as proposal_definition
from basis.modules.training.public import PlanDefinition


def contexts() -> Contexts:
    return Contexts(
        DjangoAthleteCoachContexts(),
        DjangoTrainingCoachContexts(),
        DjangoCoachExercises(),
        DjangoClock(),
    )


def proposals(source: object = None) -> Proposals:
    return Proposals(
        DjangoProposalRepository(proposal_definition, source),
        DjangoCoachPlanning(planning()),
        write_authorization(),
        DjangoUnitOfWork,
    )


def jobs(client_factory: ClientFactory | None = None) -> Jobs:
    provider = (
        DeepSeekProvider(settings.DEEPSEEK_API_KEY, client_factory)
        if client_factory
        else DeepSeekProvider(settings.DEEPSEEK_API_KEY)
    )
    return Jobs(
        DjangoJobsRepository(),
        DjangoAccountLocks(),
        DjangoCoachBilling(),
        DjangoBillingProfiles(),
        contexts(),
        provider,
        DjangoProposalSink(proposals, proposal_definition),
        DjangoClock(),
        DjangoUnitOfWork,
        CoachConfiguration(
            settings.AI_ENABLED, bool(settings.DEEPSEEK_API_KEY), settings.DEEPSEEK_MODEL
        ),
    )


def proposal_decoder() -> Callable[[object], PlanDefinition]:
    return proposal_definition
