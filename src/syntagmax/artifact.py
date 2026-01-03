# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Artifacts are the basic units of the Requirement Management System (RMS).

from pathlib import Path

from syntagmax.errors import RMSException
from syntagmax.config import Config


class ValidationError(RMSException):
    pass


class ARef:
    atype: str
    aid: str

    def __init__(self, atype: str, aid: str):
        self.atype = atype
        self.aid = aid

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

    @staticmethod
    def coerce(ref: str) -> 'ARef':
        atype, aid = ref.split('-', 1)
        return ARef(atype, aid)


class Location:
    pass


class LineLocation(Location):
    def __init__(self, loc_file: Path, loc_lines: tuple[int, int]):
        self.loc_file = loc_file
        self.loc_lines = loc_lines

    def __str__(self) -> str:
        return f'{self.loc_file.name}:{self.loc_lines[0]}-{self.loc_lines[1]}'


class Artifact:
    def __init__(self, config: Config):
        self._config = config
        self.location: Location | None = None
        self.driver: str = ''
        self.atype: str = ''
        self.aid: str = ''
        self.pids: list[ARef] = []
        self.children: set[ARef] = set()
        self.ansestors: set[ARef] = set()
        self.fields: dict[str, str] = {}

    def ref(self) -> ARef:
        return ARef(self.atype, self.aid)

    def contents(self) -> list[str]: ...

    def __str__(self) -> str:
        return f'{self.atype}-{self.aid}@{self.location}'


class ArtifactBuilder:
    def __init__(
        self,
        config: Config,
        ArtifactClass: type[Artifact],
        driver: str,
        location: Location
    ):
        self.artifact = ArtifactClass(config)
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

    def add_field(self, field: str, value: str):
        if field in self.artifact.fields:
            raise ValidationError(self._build_error('Duplicate field'))

        self.artifact.fields[field] = value
        return self

    def add_fields(self, fields: dict[str, str]):
        self.artifact.fields.update(fields)
        return self

    def _build_error(self, message: str) -> str:
        return f'Driver "{self.artifact.driver}": {self.artifact.location}: {message}'

    def build(self) -> Artifact:
        if not self.artifact.location:
            raise ValidationError(self._build_error('Location is required'))

        if not self.artifact.atype:
            raise ValidationError(self._build_error('AType is required'))

        if not self.artifact.aid:
            raise ValidationError(self._build_error('AID is required'))

        return self.artifact


type ArtifactMap = dict[ARef, Artifact]
