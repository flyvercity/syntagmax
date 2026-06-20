from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from syntagmax.artifact import Artifact


@dataclass
class Block:
    pass


@dataclass
class TextBlock(Block):
    content: str


@dataclass
class ArtifactBlock(Block):
    artifact: Artifact
    raw_text: str


@dataclass
class FileRecord:
    path: str
    blocks: list[Block] = field(default_factory=list)


@dataclass
class InputBlock:
    name: str
    files: list[FileRecord] = field(default_factory=list)


@dataclass
class BlockTree:
    inputs: list[InputBlock] = field(default_factory=list)
