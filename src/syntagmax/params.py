# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Syntagmax CLI parameters for the RMS.

from typing import TypedDict


class Params(TypedDict):
    verbose: bool
    suppress_unexpected_children: bool
    suppress_required_children: bool
    allow_top_level_arch: bool
