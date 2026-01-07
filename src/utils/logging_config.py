import logging
import os
from logging import StreamHandler, FileHandler
from datetime import datetime


def setup_run_logger(run_log_file):
    """Configure logging for a single run."""
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    fh = FileHandler(run_log_file, mode="w", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    logging.info("==== New run started. Logs will be written to %s ====", run_log_file)


def log_and_echo(text: str, level: int = logging.INFO):
    """Record and print a log message."""
    logging.log(level, "%s", text.rstrip("\n"))
