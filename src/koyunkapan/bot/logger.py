import logging
from datetime import datetime

from . import configs


class Logger:
    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    TEMPLATE = "[%(asctime)s] [%(levelname)s] %(message)s"

    def __init__(self, level="INFO"):
        self.log_file = configs.LOG_FILE

        self.level = self.LEVELS.get(level.upper(), logging.INFO)
        self.logger = logging.getLogger("CustomLogger")
        self.logger.setLevel(self.level)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        formatter = logging.Formatter(Logger.TEMPLATE, datefmt="%Y-%m-%d %H:%M:%S")

        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.level)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("--- Log started at %s ---", datetime.now())

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)
