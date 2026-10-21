"""Gunicorn parser/master/worker errors share a safe, countable event vocabulary."""

logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "safe_error": {"()": "basis.adapters.web.operational_logging.SafeGunicornErrorFilter"}
    },
    "formatters": {
        "error": {"format": "%(asctime)s [%(process)d] %(levelname)s %(message)s"},
        "access": {"format": "%(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "access",
        },
        "safe_error": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "error",
            "filters": ["safe_error"],
        },
    },
    "root": {"level": "WARNING", "handlers": ["safe_error"]},
    "loggers": {
        "gunicorn.error": {"level": "INFO", "handlers": ["safe_error"], "propagate": False},
        "gunicorn.access": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}
