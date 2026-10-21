"""Count delivery failures without recording identities, tokens or provider diagnostics."""

import logging


class SafeAccountMailFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        event = (
            "password_recovery_delivery_failed"
            if record.name == "django.contrib.auth"
            else "verification_delivery_failed"
        )
        record.msg = "account event=%s"
        record.args = (event,)
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        record.__dict__.pop("request", None)
        return True
