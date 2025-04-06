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

class Artifact:
    def __init__(self, location: str, atype: str, aid: str, pids: list[ARef] = []):
        self.location: str = location
        self.atype: str = atype
        self.aid: str = aid
        self.pids: list[ARef] = pids

    def driver(self) -> str: ...

    def metastring(self) -> str:
        return ''
