# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Interface and a simple software-oriented model for requirements tree.

from syntagmax.params import Params


class IModel():
    def is_valid_atype(self, atype: str) -> bool: ...
    def is_top_level_atype(self, atype: str) -> bool: ...
    def allowed_child(self, atype: str, child_atype: str) -> bool: ...
    def required_children(self, atype: str) -> list[str]: ...


class StandardModel(IModel):
    '''This is the simplest software-only model.'''

    def __init__(self):
        self.standard_atypes = ['ROOT', 'REQ', 'ARCH', 'VALID', 'SRC', 'TEST']
        self.top_level_atypes = ['REQ']

    def is_valid_atype(self, atype: str) -> bool:
        return atype in self.standard_atypes

    def is_top_level_atype(self, atype: str) -> bool:
        return atype in self.top_level_atypes

    def allowed_child(self, atype: str, child_atype: str) -> bool:
        match atype:
            case 'ROOT':
                allowed_children = self.top_level_atypes
            case 'REQ':
                allowed_children = ['ARCH', 'SRC', 'VALID']
            case 'ARCH':
                allowed_children = ['SRC']
            case 'VALID':
                allowed_children = ['TEST']
            case 'SRC':
                allowed_children = ['TEST']
            case _:
                allowed_children = []

        return child_atype in allowed_children

    def required_children(self, atype: str) -> list[str]:
        match atype:
            case 'ROOT':
                return ['REQ']
            case 'REQ':
                return ['SRC']
            case 'ARCH':
                return ['SRC']
            case 'SRC':
                return ['TEST']
            case _:
                return []


def build_model(params: Params) -> IModel:
    model = StandardModel()
    return model
