import logging
from datetime import datetime

from . import configs


class ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "process"):
            record.process = "main"
        return True


class _Logger:
    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    TEMPLATE = "[%(asctime)s] [%(levelname)s] [%(process)s] %(message)s"

    def __init__(self, level: str = "INFO") -> None:
        self.log_file = configs.LOG_FILE

        self.level = self.LEVELS.get(level.upper(), logging.INFO)
        self.logger = logging.getLogger("koyunkapan")
        self.logger.setLevel(self.level)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        formatter = logging.Formatter(_Logger.TEMPLATE, datefmt="%Y-%m-%d %H:%M:%S")

        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.level)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.addFilter(ContextFilter())

        self.logger.info("--- Log started at %s ---", datetime.now())

    def debug(self, message: str, *args) -> None:
        self.logger.debug(message, *args)

    def info(self, message: str, *args) -> None:
        self.logger.info(message, *args)

    def warning(self, message: str, *args) -> None:
        self.logger.warning(message, *args)

    def error(self, message: str, *args) -> None:
        self.logger.error(message, *args)

    def critical(self, message: str, *args) -> None:
        self.logger.critical(message, *args)


log = _Logger()
