# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06


class IModel():
    def is_valid_atype(self, atype: str) -> bool: ...
    def is_top_level_atype(self, atype: str) -> bool: ...
    def allowed_child(self, atype: str, child_atype: str) -> bool: ...

class StandardModel(IModel):
    STANDARD_ATYPES = ['ROOT', 'REQ', 'ARCH', 'VALID', 'DER', 'SRC', 'TEST']
    TOP_LEVEL_ATYPES = ['REQ', 'ARCH', 'DER']

    def is_valid_atype(self, atype: str) -> bool:
        return atype in StandardModel.STANDARD_ATYPES

    def is_top_level_atype(self, atype: str) -> bool:
        return atype in StandardModel.TOP_LEVEL_ATYPES

    def allowed_child(self, atype: str, child_atype: str) -> bool:
        match atype:
            case 'ROOT':
                allowed_children = StandardModel.TOP_LEVEL_ATYPES
            case 'REQ':
                allowed_children = ['SRC', 'TEST', 'VALID']
            case 'ARCH':
                allowed_children = ['SRC', 'TEST', 'VALID']
            case 'DER':
                allowed_children = ['SRC']
            case 'VALID':
                allowed_children = ['TEST']
            case 'SRC':
                allowed_children = ['TEST']
            case _:
                allowed_children = []

        return child_atype in allowed_children
