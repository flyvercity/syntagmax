# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Artifacts are the basic units of the Requirement Management System (RMS).

from syntagmax.errors import RMSException


class ValidationError(RMSException):
    pass


class ARef:
    atype: str
    aid: str

    def __init__(self, atype: str, aid: str):
        self.atype: str = atype
        self.aid: str = aid

    def __str__(self) -> str:
        return f'{self.atype}-{self.aid}'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ARef):
            return False

        return self.atype == other.atype and self.aid == other.aid

    def __hash__(self) -> int:
        return hash((self.atype, self.aid))

    @staticmethod
    def root() -> 'ARef':
        return ARef('ROOT', 'ROOT')

class Artifact:
    def __init__(self):
        self.location: str = ''
        self.driver: str = ''
        self.atype: str = ''
        self.aid: str = ''
        self.desc: str = ''
        self.pids: list[ARef] = []
        self.children: set[ARef] = set()
        self.ansestors: set[ARef] = set()

    def ref(self) -> ARef:
        return ARef(self.atype, self.aid)

    def metastring(self) -> str:
        return self.desc

    def __str__(self) -> str:
        return f'{self.atype}-{self.aid}@{self.location}'

class ArtifactBuilder:
    def __init__(self, driver: str, location: str):
        self.artifact = Artifact()
        self.artifact.driver = driver
        self.artifact.location = location

    def add_pid(self, pid: str, ptype: str):
        self.artifact.pids.append(ARef(ptype, pid))
        return self

    def add_id(self, aid: str, atype: str):
        if self.artifact.aid:
            raise ValidationError(self._build_error('Duplicate AID'))

        self.artifact.aid = aid
        self.artifact.atype = atype
        return self

    def add_desc(self, desc: str):
        if self.artifact.desc:
            raise ValidationError(self._build_error('Duplicate description'))

        self.artifact.desc = desc
        return self

    def _build_error(self, message: str) -> str:
        return f'Driver "{self.artifact.driver}": {self.artifact.location}: {message}'

    def build(self) -> Artifact:
        if not self.artifact.atype:
            raise ValidationError(self._build_error('AType is required'))

        if not self.artifact.aid:
            raise ValidationError(self._build_error('AID is required'))

        return self.artifact

type ArtifactMap = dict[ARef, Artifact]
