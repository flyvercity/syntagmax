# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06


class IModel():
    def isValidAType(self, atype: str) -> bool: ...

class StandardModel(IModel):
    STANDARD_ATYPES = ['REQ', 'ARCH', 'VALID', 'SRC', 'TEST']

    def isValidAType(self, atype: str) -> bool:
        return atype in StandardModel.STANDARD_ATYPES
