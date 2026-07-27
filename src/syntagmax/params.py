# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Syntagmax CLI parameters for the RMS.

from typing import NotRequired, TypedDict

VALID_LOG_LEVELS = ('debug', 'info', 'warning', 'error', 'silent')


class Params(TypedDict):
    log_level: NotRequired[str]
    warnings_as_errors: NotRequired[bool]
    render_tree: bool
    ai: bool
    cwd: str
    no_git: bool
    allow_dirty_worktree: bool
    language: str

    suppress_tracing: bool
    tasks: bool
    output: str
