# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Utility functions for the RMS.

from rich.console import Console

console = Console()


def pprint(what: str):
    console.print(what)  # type: ignore
