# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Artifacts are the basic units of the Requirement Management System (RMS).

class ARef:
    atype: str
    aid: str

    def __init__(self, atype: str, aid: str):
        self.atype: str = atype
        self.aid: str = aid

    def __str__(self) -> str:
        return f'{self.atype}:{self.aid}'

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
    def __init__(self, location: str, atype: str, aid: str, pids: list[ARef] = []):
        self.location: str = location
        self.atype: str = atype
        self.aid: str = aid
        self.pids: list[ARef] = pids
        self.children: set[ARef] = set()
        self.ansestors: set[ARef] = set()

    def ref(self) -> ARef:
        return ARef(self.atype, self.aid)

    def driver(self) -> str: ...

    def metastring(self) -> str:
        return ''

    def __str__(self) -> str:
        return f'{self.atype}-{self.aid}@{self.location}'

type ArtifactMap = dict[ARef, Artifact]
