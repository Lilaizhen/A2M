import logging
import os
import contextvars
from contextlib import contextmanager
from logging import StreamHandler, FileHandler
from datetime import datetime

_task_log_file = contextvars.ContextVar("task_log_file", default=None)


class TaskFileHandler(logging.Handler):
    """Write log records to the current task-specific log file, when set."""

    def __init__(self):
        super().__init__(logging.INFO)

    def emit(self, record):
        task_log_file = _task_log_file.get()
        if not task_log_file:
            return
        try:
            os.makedirs(os.path.dirname(task_log_file), exist_ok=True)
            msg = self.format(record)
            with open(task_log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            self.handleError(record)


@contextmanager
def task_log_context(task_log_file):
    token = _task_log_file.set(task_log_file)
    try:
        yield
    finally:
        _task_log_file.reset(token)


def setup_run_logger(run_log_file, mode="w"):
    """设置运行日志配置"""
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    fh = FileHandler(run_log_file, mode=mode, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    th = TaskFileHandler()
    th.setFormatter(fmt)
    root.addHandler(th)

    logging.info("==== New run started. Logs will be written to %s ====", run_log_file)


def log_and_echo(text: str, level: int = logging.INFO):
    """记录并输出日志信息"""
    logging.log(level, "%s", text.rstrip("\n"))
