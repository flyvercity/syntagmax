# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Interface and a simple software-oriented model for requirements tree.

class IModel():
    def is_valid_atype(self, atype: str) -> bool: ...
    def is_top_level_atype(self, atype: str) -> bool: ...
    def allowed_child(self, atype: str, child_atype: str) -> bool: ...
    def required_children(self, atype: str) -> list[str]: ...

class StandardModel(IModel): 
    '''This is the simplest software-only model.'''
    STANDARD_ATYPES = ['ROOT', 'REQ', 'ARCH', 'VALID', 'SRC', 'TEST']
    TOP_LEVEL_ATYPES = ['REQ']

    def is_valid_atype(self, atype: str) -> bool:
        return atype in StandardModel.STANDARD_ATYPES

    def is_top_level_atype(self, atype: str) -> bool:
        return atype in StandardModel.TOP_LEVEL_ATYPES

    def allowed_child(self, atype: str, child_atype: str) -> bool:
        match atype:
            case 'ROOT':
                allowed_children = StandardModel.TOP_LEVEL_ATYPES
            case 'REQ':
                allowed_children = ['ARCH', 'SRC', 'TEST', 'VALID']
            case 'ARCH':
                allowed_children = ['SRC', 'TEST']
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
