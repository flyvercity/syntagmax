# SPDX-License-Identifier: MIT
import pytest
import git
from pathlib import Path
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from syntagmax.change_diff import (
    FileStatus,
    FileDiff,
    BinaryArtifactChange,
    get_changed_files,
    filter_changed_files,
    compare_artifacts,
    _compare_fields,
    compare_text_blocks,
    compare_sidecar_artifacts,
    get_working_tree_changed_files,
    _estimate_line_number,
)
from syntagmax.blocks import FileRecord, TextBlock, ArtifactBlock
from syntagmax.artifact import Artifact, FileLocation
from syntagmax.change_binary import ImageProperties


@pytest.fixture
def repo_dir(tmp_path):
    """Set up a real temporary git repository."""
    repo = git.Repo.init(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".syntagmax/worktrees/\n", encoding="utf-8")
    repo.index.add([".gitignore"])
    repo.index.commit("Initial", author=git.Actor("Test", "test@test.com"))
    return repo, tmp_path


def test_file_status_enum():
    assert FileStatus.ADDED.value == "Added"
    assert FileStatus.REMOVED.value == "Removed"
    assert FileStatus.MODIFIED.value == "Modified"
    assert FileStatus.RENAMED.value == "Renamed"


def test_binary_artifact_change_status():
    change = BinaryArtifactChange(
        aid="IMG-1",
        atype="image",
        file_path="img.png",
        binary_changed=True,
        hash_base=None,
        hash_target="abc",
    )
    assert change.status == "added"

    change = BinaryArtifactChange(
        aid="IMG-1",
        atype="image",
        file_path="img.png",
        binary_changed=True,
        hash_base="abc",
        hash_target=None,
    )
    assert change.status == "removed"

    change = BinaryArtifactChange(
        aid="IMG-1",
        atype="image",
        file_path="img.png",
        binary_changed=True,
        hash_base="abc",
        hash_target="def",
    )
    assert change.status == "modified_binary"

    change = BinaryArtifactChange(
        aid="IMG-1",
        atype="image",
        file_path="img.png",
        binary_changed=False,
        hash_base="abc",
        hash_target="abc",
    )
    assert change.status == "modified_metadata"


def test_get_changed_files(repo_dir):
    repo, repo_path = repo_dir

    # 1. Create files and commit
    file_a = repo_path / "a.txt"
    file_a.write_text("A content", encoding="utf-8")
    file_b = repo_path / "b.txt"
    file_b.write_text("B content", encoding="utf-8")
    file_e = repo_path / "e.txt"
    file_e.write_text("E content", encoding="utf-8")
    repo.index.add(["a.txt", "b.txt", "e.txt"])
    commit1 = repo.index.commit("Initial add", author=git.Actor("Test", "test@test.com"))

    # 2. Modify, delete, add, rename files
    file_c = repo_path / "c.txt"
    file_c.write_text("C content", encoding="utf-8")

    file_b.unlink()

    file_a.write_text("A content modified", encoding="utf-8")

    file_f = repo_path / "f.txt"
    file_e.rename(file_f)

    repo.index.add(["c.txt", "a.txt", "f.txt"])
    repo.index.remove(["b.txt", "e.txt"])
    commit2 = repo.index.commit("Changes", author=git.Actor("Test", "test@test.com"))

    # Diff between commit1 and commit2
    diffs = get_changed_files(repo, commit1.hexsha, commit2.hexsha)

    added = [d for d in diffs if d.status == FileStatus.ADDED]
    removed = [d for d in diffs if d.status == FileStatus.REMOVED]
    modified = [d for d in diffs if d.status == FileStatus.MODIFIED]
    renamed = [d for d in diffs if d.status == FileStatus.RENAMED]

    # Verification
    assert any(d.path == "c.txt" for d in added)
    assert any(d.path == "b.txt" for d in removed)
    assert any(d.path == "a.txt" for d in modified)
    assert any(d.path == "f.txt" and d.old_path == "e.txt" for d in renamed)


def test_get_working_tree_changed_files(repo_dir):
    repo, repo_path = repo_dir

    file1 = repo_path / "w_added.txt"
    file1.write_text("Working Add", encoding="utf-8")

    file2 = repo_path / "w_modified.txt"
    file2.write_text("Orig", encoding="utf-8")
    repo.index.add(["w_modified.txt"])
    commit = repo.index.commit("Commit", author=git.Actor("Test", "test@test.com"))

    # Modify working tree
    file2.write_text("Modified working tree", encoding="utf-8")

    diffs = get_working_tree_changed_files(repo, commit.hexsha)

    modified = [d for d in diffs if d.status == FileStatus.MODIFIED]
    assert len(modified) == 1
    assert modified[0].path == "w_modified.txt"


def test_filter_changed_files(repo_dir):
    repo, repo_path = repo_dir

    @dataclass
    class DummyRecord:
        name: str
        record_base: Path

    records = [
        DummyRecord(name="reqs", record_base=repo_path / "REQ"),
        DummyRecord(name="specs", record_base=repo_path / "SPEC"),
        DummyRecord(name="not_in_repo", record_base=Path("/other/path/completely")),
    ]

    changed = [
        FileDiff(path="REQ/req1.md", status=FileStatus.ADDED),
        FileDiff(path="SPEC/spec2.md", status=FileStatus.MODIFIED),
        FileDiff(path="OTHER/other.txt", status=FileStatus.ADDED),
    ]

    filtered = filter_changed_files(changed, records, repo_path)
    assert "reqs" in filtered
    assert len(filtered["reqs"]) == 1
    assert filtered["reqs"][0].path == "REQ/req1.md"

    assert "specs" in filtered
    assert len(filtered["specs"]) == 1
    assert filtered["specs"][0].path == "SPEC/spec2.md"

    assert "not_in_repo" not in filtered
    assert "OTHER/other.txt" not in [d.path for lst in filtered.values() for d in lst]


def test_compare_fields():
    # Simple values
    base = {"priority": "high", "status": "active", "tags": "req"}
    target = {"priority": "low", "status": "active", "owner": "Alice"}

    changes = _compare_fields(base, target)
    assert changes["priority"] == ("high", "low")
    assert "status" not in changes
    assert changes["tags"] == ("req", None)
    assert changes["owner"] == (None, "Alice")

    # List values (order irrelevant, but content matters)
    base_lists = {"deps": ["A", "B"], "tags": ["req"]}
    target_lists = {"deps": ["B", "A"], "tags": ["req", "spec"]} # Same elements sorted, but different tags

    changes_lists = _compare_fields(base_lists, target_lists)
    assert "deps" not in changes_lists
    assert changes_lists["tags"] == (["req"], ["req", "spec"])


def test_compare_artifacts():
    config_mock = MagicMock()

    # Setup base artifacts
    art_base_1 = Artifact(config_mock)
    art_base_1.aid = "REQ-1"
    art_base_1.atype = "requirement"
    art_base_1.fields = {"contents": "Original content", "priority": "high"}
    art_base_1.pids = ["PARENT-1"]

    art_base_2 = Artifact(config_mock)
    art_base_2.aid = "REQ-2"
    art_base_2.atype = "requirement"
    art_base_2.fields = {"contents": "Removed content"}

    block_base_1 = ArtifactBlock(artifact=art_base_1, raw_text="")
    block_base_2 = ArtifactBlock(artifact=art_base_2, raw_text="")

    base_records = [
        FileRecord(path="file1.md", blocks=[block_base_1]),
        FileRecord(path="file2.md", blocks=[block_base_2]),
    ]

    # Setup target artifacts
    art_target_1 = Artifact(config_mock)
    art_target_1.aid = "REQ-1"
    art_target_1.atype = "requirement"
    art_target_1.fields = {"contents": "Modified content", "priority": "low"}
    art_target_1.pids = ["PARENT-2"] # Parent changed

    art_target_3 = Artifact(config_mock)
    art_target_3.aid = "REQ-3"
    art_target_3.atype = "requirement"
    art_target_3.fields = {"contents": "New content"}

    block_target_1 = ArtifactBlock(artifact=art_target_1, raw_text="")
    block_target_3 = ArtifactBlock(artifact=art_target_3, raw_text="")

    target_records = [
        FileRecord(path="file1.md", blocks=[block_target_1]),
        FileRecord(path="file3.md", blocks=[block_target_3]),
    ]

    diff = compare_artifacts(base_records, target_records)

    # Added
    assert len(diff.added) == 1
    assert diff.added[0][0] == "REQ-3"
    assert diff.added[0][1] == "requirement"

    # Removed
    assert len(diff.removed) == 1
    assert diff.removed[0][0] == "REQ-2"

    # Modified
    assert len(diff.modified) == 1
    change = diff.modified[0]
    assert change.aid == "REQ-1"
    assert change.content_changed is True
    assert change.changed_fields["priority"] == ("high", "low")
    assert change.changed_fields["_parents"] == (["PARENT-1"], ["PARENT-2"])


def test_estimate_line_number():
    # Simple blocks with contents or raw_text
    block1 = TextBlock(content="Line1\nLine2\nLine3")
    block2 = TextBlock(content="Line4")

    # Estimating for block2 index=1
    assert _estimate_line_number(block2, [block1, block2], 1) == 4


def test_compare_text_blocks_pure_add_remove():
    block_base = TextBlock(content="Line1\nLine2", marker="COM")
    base_records = [FileRecord(path="file.md", blocks=[block_base])]

    block_target = TextBlock(content="Line3\nLine4", marker="COM")
    target_records = [FileRecord(path="file.md", blocks=[block_target])]

    # Sequence matcher comparisons
    diff = compare_text_blocks(base_records, target_records)
    assert len(diff.modified) == 1
    assert diff.modified[0].old_content == "Line1\nLine2"
    assert diff.modified[0].new_content == "Line3\nLine4"

    # Empty base, target has blocks
    diff_add = compare_text_blocks([], target_records)
    assert len(diff_add.added) == 1
    assert diff_add.added[0].new_content == "Line3\nLine4"

    # Base has blocks, empty target
    diff_rem = compare_text_blocks(base_records, [])
    assert len(diff_rem.removed) == 1
    assert diff_rem.removed[0].old_content == "Line1\nLine2"


def test_compare_text_blocks_with_ids():
    # Matching by explicit ID
    block_base_1 = TextBlock(content="Base 1", id="ID-A", explicit_id=True, marker="COM")
    block_base_2 = TextBlock(content="Base 2", id="ID-B", explicit_id=True, marker="COM")

    block_target_1 = TextBlock(content="Base 1 Modified", id="ID-A", explicit_id=True, marker="COM")
    block_target_3 = TextBlock(content="Base 3", id="ID-C", explicit_id=True, marker="COM")

    base_records = [FileRecord(path="file.md", blocks=[block_base_1, block_base_2])]
    target_records = [FileRecord(path="file.md", blocks=[block_target_1, block_target_3])]

    diff = compare_text_blocks(base_records, target_records)

    # ID-A modified
    assert len(diff.modified) == 1
    assert diff.modified[0].old_content == "Base 1"
    assert diff.modified[0].new_content == "Base 1 Modified"

    # ID-B removed
    assert len(diff.removed) == 1
    assert diff.removed[0].old_content == "Base 2"

    # ID-C added
    assert len(diff.added) == 1
    assert diff.added[0].new_content == "Base 3"


def test_compare_text_blocks_sequence_matcher_complex():
    # Test all other opcodes (delete, insert, replace with extra blocks) in SequenceMatcher
    # We want unmatched blocks (explicit_id=False or ID mismatch)
    # base has "Block 1", "Block 2", "Block 3"
    # target has "Block 1 Modified", "Block 3", "Block 4"
    block_base_1 = TextBlock(content="Block 1", marker="COM")
    block_base_2 = TextBlock(content="Block 2", marker="COM")
    block_base_3 = TextBlock(content="Block 3", marker="COM")

    block_target_1 = TextBlock(content="Block 1 Modified", marker="COM")
    block_target_3 = TextBlock(content="Block 3", marker="COM") # Equal block -> no change
    block_target_4 = TextBlock(content="Block 4", marker="COM")

    base_records = [FileRecord(path="file.md", blocks=[block_base_1, block_base_2, block_base_3])]
    target_records = [FileRecord(path="file.md", blocks=[block_target_1, block_target_3, block_target_4])]

    diff = compare_text_blocks(base_records, target_records)

    # SequenceMatcher on ["Block 1", "Block 2", "Block 3"] and ["Block 1 Modified", "Block 3", "Block 4"]
    # matches "Block 3" at index 2 (base) and index 1 (target).
    # Slice 0:2 of base is ["Block 1", "Block 2"].
    # Slice 0:1 of target is ["Block 1 Modified"].
    # Tag 'replace' for 0:2 with 0:1 -> "Block 1" modified to "Block 1 Modified".
    # Since "Block 2" has no corresponding target block, it's removed.
    # After "Block 3", target has "Block 4" which is added.
    assert len(diff.modified) == 1
    assert diff.modified[0].old_content == "Block 1"
    assert diff.modified[0].new_content == "Block 1 Modified"

    assert len(diff.removed) == 1
    assert diff.removed[0].old_content == "Block 2"

    assert len(diff.added) == 1
    assert diff.added[0].new_content == "Block 4"


def test_compare_text_blocks_sequence_matcher_asymmetric_replace():
    # base: ["Block 1", "Block 2"]
    # target: ["Block 1 Modified"] (1 replace, 1 extra base block -> deleted)
    block_base_1 = TextBlock(content="Block 1", marker="COM")
    block_base_2 = TextBlock(content="Block 2", marker="COM")

    block_target_1 = TextBlock(content="Block 1 Modified", marker="COM")

    base_records = [FileRecord(path="file.md", blocks=[block_base_1, block_base_2])]
    target_records = [FileRecord(path="file.md", blocks=[block_target_1])]

    diff = compare_text_blocks(base_records, target_records)

    # 1 modified, 1 removed
    assert len(diff.modified) == 1
    assert diff.modified[0].old_content == "Block 1"
    assert diff.modified[0].new_content == "Block 1 Modified"

    assert len(diff.removed) == 1
    assert diff.removed[0].old_content == "Block 2"


def test_compare_text_blocks_sequence_matcher_delete_and_insert():
    # base content: ["A", "B", "C"]
    # target content: ["A", "C"]
    # SequenceMatcher matches "A" and "C", and identifies "B" as deleted.
    block_base_1 = TextBlock(content="A", marker="COM")
    block_base_2 = TextBlock(content="B", marker="COM")
    block_base_3 = TextBlock(content="C", marker="COM")

    block_target_1 = TextBlock(content="A", marker="COM")
    block_target_3 = TextBlock(content="C", marker="COM")

    base_records = [FileRecord(path="file.md", blocks=[block_base_1, block_base_2, block_base_3])]
    target_records = [FileRecord(path="file.md", blocks=[block_target_1, block_target_3])]

    diff = compare_text_blocks(base_records, target_records)
    assert len(diff.removed) == 1
    assert diff.removed[0].old_content == "B"
    assert len(diff.added) == 0
    assert len(diff.modified) == 0


def test_compare_sidecar_artifacts(tmp_path):
    config_mock = MagicMock()
    base_path = tmp_path / "base"
    target_path = tmp_path / "target"
    base_dir_offset = Path("")

    base_path.mkdir()
    target_path.mkdir()

    # Create dummy images
    img_base = base_path / "img.png"
    img_base.write_bytes(b"base-bytes")
    img_target = target_path / "img.png"
    img_target.write_bytes(b"target-bytes-modified")

    # Set up records
    art_base = Artifact(config_mock)
    art_base.aid = "IMG-1"
    art_base.atype = "image"
    art_base.location = FileLocation(loc_file="img.png", loc_sidecar="img.png.yaml")
    art_base.fields = {"title": "Base Title"}

    art_target = Artifact(config_mock)
    art_target.aid = "IMG-1"
    art_target.atype = "image"
    art_target.location = FileLocation(loc_file="img.png", loc_sidecar="img.png.yaml")
    art_target.fields = {"title": "Target Title"}

    base_records = [FileRecord(path="img.png.yaml", blocks=[ArtifactBlock(artifact=art_base, raw_text="")])]
    target_records = [FileRecord(path="img.png.yaml", blocks=[ArtifactBlock(artifact=art_target, raw_text="")])]

    # Mock extract_image_properties from change_binary module
    with patch("syntagmax.change_binary.extract_image_properties") as mock_extract:
        mock_extract.side_effect = lambda p: ImageProperties(size_bytes=len(p.read_bytes())) if p.exists() else None

        changes = compare_sidecar_artifacts(
            base_records, target_records, base_path, target_path, base_dir_offset
        )

        assert len(changes) == 1
        change = changes[0]
        assert change.aid == "IMG-1"
        assert change.binary_changed is True
        assert change.field_changes["title"] == ("Base Title", "Target Title")
        assert change.base_properties.size_bytes == len(b"base-bytes")
        assert change.target_properties.size_bytes == len(b"target-bytes-modified")


def test_compare_sidecar_artifacts_binary_unchanged_fields_changed(tmp_path):
    config_mock = MagicMock()
    base_path = tmp_path / "base"
    target_path = tmp_path / "target"
    base_dir_offset = Path("")

    base_path.mkdir()
    target_path.mkdir()

    # Create identical dummy images
    img_base = base_path / "img.png"
    img_base.write_bytes(b"identical-bytes")
    img_target = target_path / "img.png"
    img_target.write_bytes(b"identical-bytes")

    # Set up records with different titles but same image
    art_base = Artifact(config_mock)
    art_base.aid = "IMG-1"
    art_base.atype = "image"
    art_base.location = FileLocation(loc_file="img.png", loc_sidecar="img.png.yaml")
    art_base.fields = {"title": "Base Title"}

    art_target = Artifact(config_mock)
    art_target.aid = "IMG-1"
    art_target.atype = "image"
    art_target.location = FileLocation(loc_file="img.png", loc_sidecar="img.png.yaml")
    art_target.fields = {"title": "Target Title"}

    base_records = [FileRecord(path="img.png.yaml", blocks=[ArtifactBlock(artifact=art_base, raw_text="")])]
    target_records = [FileRecord(path="img.png.yaml", blocks=[ArtifactBlock(artifact=art_target, raw_text="")])]

    with patch("syntagmax.change_binary.extract_image_properties") as mock_extract:
        mock_extract.side_effect = lambda p: ImageProperties(size_bytes=len(p.read_bytes())) if p.exists() else None

        changes = compare_sidecar_artifacts(
            base_records, target_records, base_path, target_path, base_dir_offset
        )

        assert len(changes) == 1
        change = changes[0]
        assert change.aid == "IMG-1"
        assert change.binary_changed is False
        assert change.field_changes["title"] == ("Base Title", "Target Title")


def test_compare_sidecar_artifacts_pure_add_remove(tmp_path):
    config_mock = MagicMock()
    base_path = tmp_path / "base"
    target_path = tmp_path / "target"
    base_dir_offset = Path("")

    base_path.mkdir()
    target_path.mkdir()

    img_target = target_path / "img_new.png"
    img_target.write_bytes(b"new-image-bytes")

    art_target = Artifact(config_mock)
    art_target.aid = "IMG-NEW"
    art_target.atype = "image"
    art_target.location = FileLocation(loc_file="img_new.png", loc_sidecar="img_new.png.yaml")
    art_target.fields = {"title": "New Title"}

    target_records = [FileRecord(path="img_new.png.yaml", blocks=[ArtifactBlock(artifact=art_target, raw_text="")])]

    with patch("syntagmax.change_binary.extract_image_properties") as mock_extract:
        mock_extract.side_effect = lambda p: ImageProperties(size_bytes=len(p.read_bytes())) if p.exists() else None

        # Test Added
        changes = compare_sidecar_artifacts(
            [], target_records, base_path, target_path, base_dir_offset
        )
        assert len(changes) == 1
        assert changes[0].aid == "IMG-NEW"
        assert changes[0].status == "added"

        # Test Removed
        # Move img_target to base
        img_base = base_path / "img_new.png"
        img_base.write_bytes(b"new-image-bytes")
        img_target.unlink()

        changes_rem = compare_sidecar_artifacts(
            target_records, [], base_path, target_path, base_dir_offset
        )
        assert len(changes_rem) == 1
        assert changes_rem[0].aid == "IMG-NEW"
        assert changes_rem[0].status == "removed"
