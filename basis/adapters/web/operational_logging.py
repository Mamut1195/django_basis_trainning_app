"""Keep production HTTP failures observable without URLs, tokens or exception data."""

import logging


class SafeHTTPFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        status = getattr(record, "status_code", None)
        code = status if isinstance(status, int) and 100 <= status <= 599 else 0
        record.msg = "HTTP failure status=%s"
        record.args = (code,)
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        record.__dict__.pop("request", None)
        return True


class SafeGunicornErrorFilter(logging.Filter):
    """Classify trusted event prefixes, never interpolate request/exception arguments.

    Gunicorn 26.2 formats parser exceptions before logging. Only known reason
    prefixes recover their class/status; unknown errors deliberately use status=0.
    Every record remains countable, with severity, process, event and safe class.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        template = record.msg if isinstance(record.msg, str) else ""
        event, status, error_class = "server_event", 0, "Unavailable"
        if template.startswith("Invalid request from ip="):
            event = "request_rejected"
            reason = template.partition(": ")[2]
            for prefix, name, http_code in (
                ("Invalid HTTP request line:", "InvalidRequestLine", 400),
                ("Invalid HTTP method:", "InvalidRequestMethod", 400),
                ("Invalid HTTP Version:", "InvalidHTTPVersion", 400),
                ("Invalid HTTP Header:", "InvalidHeader", 400),
                ("Invalid HTTP header name:", "InvalidHeaderName", 400),
                ("Unsupported transfer coding:", "UnsupportedTransferCoding", 501),
                ("Configuration problem:", "ConfigurationProblem", 500),
                ("Unable to comply with expectation:", "ExpectationFailed", 417),
            ):
                if reason.startswith(prefix):
                    error_class, status = name, http_code
                    break
        else:
            for prefix, event_code, http_status in (
                ("Error handling request", "request_exception", 500),
                ("WORKER TIMEOUT", "worker_timeout", 0),
                ("Booting worker", "worker_boot", 0),
                ("Worker exiting", "worker_exit", 0),
                ("Worker (pid:", "worker_lifecycle", 0),
                ("Starting gunicorn", "server_start", 0),
                ("Listening at:", "listener_ready", 0),
                ("Using worker:", "worker_selected", 0),
                ("Handling signal:", "signal_received", 0),
                ("Shutting down:", "server_shutdown", 0),
                ("Connection in use:", "listener_error", 0),
                ("Can't connect", "listener_error", 0),
            ):
                if template.startswith(prefix):
                    event, status = event_code, http_status
                    break
            if record.exc_info and record.exc_info[0] is not None:
                name = record.exc_info[0].__name__
                error_class = (
                    name
                    if name
                    in {
                        "RuntimeError",
                        "ValueError",
                        "TypeError",
                        "OSError",
                        "TimeoutError",
                        "SystemExit",
                        "MemoryError",
                        "ImportError",
                        "ModuleNotFoundError",
                        "AssertionError",
                        "AttributeError",
                        "KeyError",
                        "ConnectionError",
                    }
                    else "OtherException"
                )
        record.msg = "gunicorn event=%s status=%s exception=%s"
        record.args = (event, status, error_class)
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        record.__dict__.pop("request", None)
        return True
