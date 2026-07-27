# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-07-27
# Description: Logging utilities for Syntagmax CLI.

import logging as lg

from rich.logging import RichHandler

from syntagmax.params import VALID_LOG_LEVELS  # noqa: F401

LOG_LEVEL_MAP = {
    'debug': lg.DEBUG,
    'info': lg.INFO,
    'warning': lg.WARNING,
    'error': lg.ERROR,
    'silent': lg.CRITICAL + 1,
}


class WarningsAsErrorsHandler(lg.Handler):
    def __init__(self):
        super().__init__(level=lg.WARNING)
        self.warnings: list[str] = []

    def emit(self, record: lg.LogRecord):
        if record.levelno == lg.WARNING:
            self.warnings.append(record.getMessage())


_warnings_handler: WarningsAsErrorsHandler | None = None


def get_warnings_handler() -> WarningsAsErrorsHandler | None:
    return _warnings_handler


def set_warnings_handler(handler: WarningsAsErrorsHandler | None):
    global _warnings_handler
    _warnings_handler = handler


def _cleanup_logging():
    global _warnings_handler
    root_logger = lg.getLogger()
    for h in list(root_logger.handlers):
        if isinstance(h, WarningsAsErrorsHandler):
            root_logger.removeHandler(h)
    _warnings_handler = None


def configure_log_display(level_str: str, warnings_as_errors: bool = False):
    """Configure logging display level on RichHandler and root logger."""
    display_level = LOG_LEVEL_MAP.get(level_str, lg.INFO)

    # Root logger level: min(display_level, WARNING) if wae active, else display_level
    if warnings_as_errors:
        root_level = min(display_level, lg.WARNING)
    else:
        root_level = display_level

    root_logger = lg.getLogger()
    root_logger.setLevel(root_level)

    # Update RichHandler level
    for h in root_logger.handlers:
        if isinstance(h, RichHandler):
            h.setLevel(display_level)
            break
