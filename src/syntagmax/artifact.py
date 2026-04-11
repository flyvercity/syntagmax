# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Artifacts are the basic units of the Requirement Management System (RMS).

from dataclasses import dataclass
from datetime import datetime

from syntagmax.errors import RMSException
from syntagmax.config import Config


class ValidationError(RMSException):
    pass


class Location:
    def filepath(self) -> str:
        raise NotImplementedError


class FileLocation(Location):
    def __init__(self, loc_file: str, loc_sidecar: str | None = None):
        self.loc_file = loc_file
        self.loc_sidecar = loc_sidecar

    def filepath(self) -> str:
        return self.loc_file

    def __str__(self) -> str:
        if self.loc_sidecar:
            return f'{self.loc_file}|{self.loc_sidecar}'
        return self.loc_file


class LineLocation(Location):
    def __init__(self, loc_file: str, loc_lines: tuple[int, int]):
        self.loc_file = loc_file
        self.loc_lines = loc_lines

    def filepath(self) -> str:
        return self.loc_file

    def __str__(self) -> str:
        return f'{self.loc_file}:{self.loc_lines[0]}-{self.loc_lines[1]}'


class NotebookLocation(LineLocation):
    def __init__(self, loc_file: str, loc_lines: tuple[int, int], loc_cell: int):
        super().__init__(loc_file, loc_lines)
        self.loc_cell = loc_cell

    def filepath(self) -> str:
        return self.loc_file

    def __str__(self) -> str:
        return f'{self.loc_file}[{self.loc_cell}]:{self.loc_lines[0]}-{self.loc_lines[1]}'


@dataclass(frozen=True)
class Revision:
    hash_long: str
    hash_short: str
    timestamp: datetime
    author_email: str

    def __str__(self) -> str:
        return f'{self.hash_short} by {self.author_email} at {self.timestamp}'


@dataclass
class ParentLink:
    pid: str
    nominal_revision: str | None = None
    is_suspicious: bool = False


UNDEFINED_ID = '<undefined>'


class Artifact:
    def __init__(self, config: Config):
        self._config = config
        self.location: Location | None = None
        self.driver: str = ''
        self.atype: str = ''
        self.aid: str = ''
        self.pids: list[str] = []
        self.parent_links: list[ParentLink] = []
        self.children: set[str] = set()
        self.ansestors: set[str] = set()
        self.fields: dict[str, str | list[str]] = {}
        self.revisions: set[Revision] = set()

    @property
    def latest_revision(self) -> Revision | None:
        if not self.revisions:
            return None
        return max(self.revisions, key=lambda r: r.timestamp)

    def contents(self) -> str:
        return self.fields.get('contents', '<empty>')

    def __str__(self) -> str:
        hash_short = self.latest_revision.hash_short if self.latest_revision else 'none'
        return f'{self.atype}።{self.aid}።{self.location}@{hash_short}'


class ArtifactBuilder:
    def __init__(
        self,
        config: Config,
        ArtifactClass: type[Artifact],
        driver: str,
        location: Location,
        metamodel: dict | None = None,
    ):
        self.artifact = ArtifactClass(config)
        self.artifact.driver = driver
        self.artifact.location = location
        self._metamodel = metamodel

    def add_id(self, aid: str, atype: str):
        if self.artifact.aid:
            raise ValidationError(self._build_error('Duplicate AID'))

        self.artifact.aid = aid
        self.artifact.atype = atype
        return self

    def add_field(self, field: str, value: str):
        multiple = False
        if self._metamodel and self.artifact.atype in self._metamodel.get('artifacts', {}):
            atype_def = self._metamodel['artifacts'][self.artifact.atype]
            attr_rules = atype_def.get('attributes', {}).get(field, [])
            
            # Handle both list (new) and dict (old/mock) for backward compatibility in tests
            if isinstance(attr_rules, dict):
                attr_rules = [attr_rules]
                
            # If ANY rule says it's multiple, we treat it as multiple
            for rule in attr_rules:
                if rule.get('multiple', False):
                    multiple = True
                    break

        if multiple:
            if field not in self.artifact.fields:
                self.artifact.fields[field] = []
            elif not isinstance(self.artifact.fields[field], list):
                # ensure it's a list for multiple field
                self.artifact.fields[field] = [self.artifact.fields[field]]

            # The current field is already checked to be list in the block above or is new
            self.artifact.fields[field].append(value)  # type: ignore
        else:
            if field in self.artifact.fields:
                raise ValidationError(self._build_error(f'Duplicate field "{field}"'))

            self.artifact.fields[field] = value
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

        # Ensure all multiple fields are present as lists
        if self._metamodel and self.artifact.atype in self._metamodel.get('artifacts', {}):
            atype_def = self._metamodel['artifacts'][self.artifact.atype]
            for attr_name, attr_rules in atype_def.get('attributes', {}).items():
                if isinstance(attr_rules, dict):
                    attr_rules = [attr_rules]
                is_multiple = any(r.get('multiple', False) for r in attr_rules)
                if is_multiple:
                    if attr_name not in self.artifact.fields:
                        self.artifact.fields[attr_name] = []

        return self.artifact


type ArtifactMap = dict[str, Artifact]
