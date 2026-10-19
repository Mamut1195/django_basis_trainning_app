"""Supported identity commands and results."""

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
