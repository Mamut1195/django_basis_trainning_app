"""Explicit composition of manual training, authorization and RM reference ports."""

from basis.bootstrap.billing import write_authorization
from basis.modules.athletes.adapters.references import DjangoRMReferences
from basis.modules.training.adapters.django import UUIDSessionIds
from basis.modules.training.adapters.locking import TrainingUnitOfWork
from basis.modules.training.adapters.manual_repository import DjangoManualRepository
from basis.modules.training.application.manual import ManualTraining


def manual_training() -> ManualTraining:
    return ManualTraining(
        DjangoManualRepository(),
        TrainingUnitOfWork,
        write_authorization(),
        UUIDSessionIds(),
        DjangoRMReferences(),
    )
