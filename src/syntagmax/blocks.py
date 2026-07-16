# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-06-20
# Description: Block tree data model for publishing.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from syntagmax.artifact import Artifact


@dataclass
class Block:
    pass


@dataclass
class HeadingBlock(Block):
    content: str
    level: int
    source_offset: int | None = None


@dataclass
class TextBlock(Block):
    content: str
    marker: str | None = None
    id: str | None = None
    explicit_id: bool = False
    source_offset: int | None = None
    """Character offset of the opening marker tag (e.g., `[COM]`) in the source file.
    None for unmarked text blocks or when offset tracking is not active."""


@dataclass
class ArtifactBlock(Block):
    artifact: Artifact
    raw_text: str


@dataclass
class ErrorBlock(Block):
    message: str
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
