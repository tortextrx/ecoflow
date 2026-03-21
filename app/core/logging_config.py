import logging, json, sys
from datetime import datetime, timezone
from pathlib import Path

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k in ("session_id", "operation_id", "job_id"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d, ensure_ascii=False)

def setup_logging(log_path: str | None = None, debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logger = logging.getLogger("ecoflow")
    logger.setLevel(level)
    logger.handlers.clear()
    fmt = JSONFormatter()
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger
