# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-06-20
# Description: Tests for block tree data model for publishing.

import pytest
from unittest.mock import MagicMock
from syntagmax.blocks import (
    Block,
    TextBlock,
    ArtifactBlock,
    ErrorBlock,
    FileRecord,
    InputBlock,
    BlockTree,
)
from syntagmax.artifact import Artifact


def test_base_block():
    """Verify that the base Block class can be instantiated."""
    block = Block()
    assert isinstance(block, Block)


def test_text_block_defaults():
    """Verify default values and custom initialization of TextBlock."""
    # Test defaults
    tb = TextBlock(content="Hello World")
    assert tb.content == "Hello World"
    assert tb.marker is None
    assert tb.id is None
    assert tb.explicit_id is False
    assert tb.source_offset is None

    # Test custom values
    tb_custom = TextBlock(
        content="Custom block",
        marker="COM",
        id="SYS-001",
        explicit_id=True,
        source_offset=42,
    )
    assert tb_custom.content == "Custom block"
    assert tb_custom.marker == "COM"
    assert tb_custom.id == "SYS-001"
    assert tb_custom.explicit_id is True
    assert tb_custom.source_offset == 42


def test_artifact_block():
    """Verify ArtifactBlock fields with standard or mocked Artifact."""
    mock_artifact = MagicMock(spec=Artifact)
    ab = ArtifactBlock(artifact=mock_artifact, raw_text="[SYS-001] some artifact raw markdown")
    assert ab.artifact == mock_artifact
    assert ab.raw_text == "[SYS-001] some artifact raw markdown"


def test_error_block():
    """Verify ErrorBlock correctly captures error message and raw text."""
    eb = ErrorBlock(message="Syntax error at line 5", raw_text="[SYS-001]] invalid close")
    assert eb.message == "Syntax error at line 5"
    assert eb.raw_text == "[SYS-001]] invalid close"


def test_file_record():
    """Verify FileRecord defaults and custom list of blocks."""
    # Default list
    fr_default = FileRecord(path="doc/intro.md")
    assert fr_default.path == "doc/intro.md"
    assert fr_default.blocks == []

    # Custom blocks
    tb = TextBlock(content="Intro text")
    fr_custom = FileRecord(path="doc/intro.md", blocks=[tb])
    assert fr_custom.blocks == [tb]


def test_input_block():
    """Verify InputBlock defaults and custom list of files."""
    # Default list
    ib_default = InputBlock(name="input_1")
    assert ib_default.name == "input_1"
    assert ib_default.files == []

    # Custom files
    fr = FileRecord(path="doc/intro.md")
    ib_custom = InputBlock(name="input_1", files=[fr])
    assert ib_custom.files == [fr]


def test_block_tree():
    """Verify BlockTree defaults and custom list of inputs."""
    # Default list
    bt_default = BlockTree()
    assert bt_default.inputs == []

    # Custom inputs
    ib = InputBlock(name="input_1")
    bt_custom = BlockTree(inputs=[ib])
    assert bt_custom.inputs == [ib]


def test_full_block_tree_nested_initialization():
    """Verify nested instantiation of a full BlockTree structure."""
    tb = TextBlock(content="Some header block\n")
    eb = ErrorBlock(message="Error info", raw_text="raw err")
    fr = FileRecord(path="src/intro.md", blocks=[tb, eb])
    ib = InputBlock(name="driver_obsidian", files=[fr])
    bt = BlockTree(inputs=[ib])

    assert len(bt.inputs) == 1
    assert bt.inputs[0].name == "driver_obsidian"
    assert len(bt.inputs[0].files) == 1
    assert bt.inputs[0].files[0].path == "src/intro.md"
    assert len(bt.inputs[0].files[0].blocks) == 2
    assert bt.inputs[0].files[0].blocks[0] == tb
    assert bt.inputs[0].files[0].blocks[1] == eb
