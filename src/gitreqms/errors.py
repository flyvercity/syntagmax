# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Error classes for gitreqms.

class RMSException(Exception):
    pass

class InvalidArtifactIdentifier(RMSException):
    pass

class NonFatalError(RMSException):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__('Errors were reported')
