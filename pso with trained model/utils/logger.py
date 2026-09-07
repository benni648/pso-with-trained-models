"""
Centralized logging system for the PSO Traffic application.

Features:
  - Rotating file handler (10 MB max, 10 backups)
  - Console handler with color support
  - Structured format: timestamp | level | module | message
  - Configurable log levels
  - LoggerManager for centralized control
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler


# ── LOG FORMATS ──────────────────────────────────────────────────

CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── COLOR CODES (for console) ───────────────────────────────────

COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",
}


class ColorFormatter(logging.Formatter):
    """Custom formatter that adds color to console output."""

    def format(self, record):
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname}{COLORS['RESET']}"
        return super().format(record)


class SafeStreamHandler(logging.StreamHandler):
    """
    Stream handler that tolerates characters the console cannot encode.

    Windows consoles (e.g., cp1252) crash with UnicodeEncodeError when
    a log message contains unicode such as ✓ or emoji. This handler
    re-emits the message with unencodable characters replaced so the
    application never loses log output (the utf-8 file handler still
    captures the full message).
    """

    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            try:
                msg = self.format(record)
                stream = self.stream
                encoding = getattr(stream, "encoding", None) or "utf-8"
                safe_msg = msg.encode(encoding, errors="replace").decode(encoding, errors="replace")
                stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)


# ── LOGGER MANAGER ──────────────────────────────────────────────

class LoggerManager:
    """
    Centralized logger management.

    Usage:
        logger = LoggerManager.get_logger(__name__)
        logger.info("Something happened")
    """

    _loggers = {}
    _initialized = False
    _log_dir = None
    _log_file = None
    _log_level = "INFO"

    @classmethod
    def _setup(cls):
        """Initialize logging system once."""
        if cls._initialized:
            return

        # Import config if available, otherwise use defaults
        try:
            from config.config import config
            cls._log_dir = config.LOGS_DIR
            cls._log_file = config.LOG_FILE
            cls._log_level = config.LOG_LEVEL
        except ImportError:
            cls._log_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "logs"
            )
            cls._log_file = os.path.join(cls._log_dir, "app.log")
            cls._log_level = os.getenv("LOG_LEVEL", "INFO")

        # Ensure log directory exists
        os.makedirs(cls._log_dir, exist_ok=True)

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, cls._log_level.upper(), logging.INFO))

        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # ── Console Handler ──────────────────────────────
        console_handler = SafeStreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, cls._log_level.upper(), logging.INFO))
        console_formatter = ColorFormatter(CONSOLE_FORMAT, DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # ── File Handler (rotating) ──────────────────────
        file_handler = RotatingFileHandler(
            cls._log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)  # File captures everything
        file_formatter = logging.Formatter(FILE_FORMAT, DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a pre-configured logger instance.

        Parameters
        ----------
        name : str
            Logger name, typically __name__ of the calling module.

        Returns
        -------
        logging.Logger
            Configured logger instance.
        """
        cls._setup()

        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)

        return cls._loggers[name]

    @classmethod
    def set_level(cls, level: str):
        """Change log level at runtime."""
        cls._log_level = level
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                handler.setLevel(getattr(logging, level.upper(), logging.INFO))
