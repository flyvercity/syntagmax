from typing import TypedDict

class Params(TypedDict):
    verbose: bool
    suppress_unexpected_children: bool
    suppress_required_children: bool
    allow_top_level_arch: bool
