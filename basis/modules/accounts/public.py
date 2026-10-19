"""Supported identity commands and results."""

from .application.coach import AccountLocks
from .application.identity import (
    ConsumeAttempt,
    Identity,
    LinkLegacyProfile,
    RegisterAccount,
    VerifyAccount,
)
from .application.recovery import RecoverPassword, Recovery
from .domain.identity import Account, AccountUnavailable, InvalidVerification

__all__ = (
    "AccountLocks",
    "LinkLegacyProfile",
    "RecoverPassword",
    "Recovery",
    "Account",
    "AccountUnavailable",
    "ConsumeAttempt",
    "Identity",
    "InvalidVerification",
    "RegisterAccount",
    "VerifyAccount",
)
