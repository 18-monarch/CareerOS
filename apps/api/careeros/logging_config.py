import json
import logging


class JSONFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for key in (
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "source_id",
            "error_type",
            "added",
            "parse_errors",
            "host",
            "attempt",
            "command",
        ):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("careeros")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
