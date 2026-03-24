# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Error classes for syntagmax.


class RMSException(Exception):
    pass


class InvalidArtifactIdentifier(RMSException):
    pass


class FatalError(RMSException):
    def __init__(self, errors: list[str] | str):
        if isinstance(errors, str):
            self.errors = [errors]
        else:
            self.errors = errors
        super().__init__('\n'.join(self.errors))
