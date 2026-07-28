# SPDX-License-Identifier: MIT

"""Tests for simple-markdown driver editing support (update_artifacts, update_artifact_attributes)."""

import pytest
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.simple_markdown import SimpleMarkdownExtractor
from syntagmax.params import Params


@pytest.fixture
def params():
    return Params(
        verbose=False,
        render_tree=False,
        ai=False,
        output='console',
        cwd='.',
        no_git=True,
        allow_dirty_worktree=False,
        language='en',
        suppress_tracing=False,
    )


@pytest.fixture
def config_file(tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        """
base = "."
[[input]]
name = "test"
dir = "."
driver = "simple-markdown"
atype = "REQ"
""",
        encoding='utf-8',
    )
    return cfg_path


@pytest.fixture
def config(params, config_file):
    return Config(params=params, config_filename=config_file)


@pytest.fixture
def input_record(tmp_path):
    return InputRecord(
        name='test',
        dir='.',
        record_base=tmp_path,
        filepaths=[],
        driver='simple-markdown',
        default_atype='REQ',
        marker='REQ',
    )


class TestUpdateArtifacts:
    """Tests for update_artifacts (ID renumbering)."""

    def test_update_existing_id(self, config, input_record, tmp_path):
        """Update an existing id key in frontmatter."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: OLD-001\ntitle: My Req\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        extractor.update_artifacts(loc_file, [(artifact, 'REQ-001')])

        content = filepath.read_text(encoding='utf-8')
        assert 'REQ-001' in content
        assert 'OLD-001' not in content
        assert 'title: My Req' in content
        assert 'Body.' in content

    def test_insert_id_when_missing(self, config, input_record, tmp_path):
        """Insert id key when frontmatter has no id field."""
        filepath = tmp_path / 'no-id.md'
        filepath.write_text("---\ntitle: No ID\nstatus: draft\n---\nBody text.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        extractor.update_artifacts(loc_file, [(artifact, 'REQ-042')])

        content = filepath.read_text(encoding='utf-8')
        assert 'REQ-042' in content
        assert 'title: No ID' in content
        assert 'status: draft' in content
        assert 'Body text.' in content

    def test_case_insensitive_id_update(self, config, input_record, tmp_path):
        """Update an ID key regardless of casing (ID vs id)."""
        filepath = tmp_path / 'upper.md'
        filepath.write_text("---\nID: TASK-X\ntitle: Upper\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        extractor.update_artifacts(loc_file, [(artifact, 'REQ-099')])

        content = filepath.read_text(encoding='utf-8')
        assert 'REQ-099' in content
        assert 'TASK-X' not in content

    def test_no_frontmatter_creates_one(self, config, input_record, tmp_path):
        """File without frontmatter gets one created with the id."""
        filepath = tmp_path / 'plain.md'
        filepath.write_text("Just plain text.\nNo frontmatter.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        extractor.update_artifacts(loc_file, [(artifact, 'REQ-001')])

        content = filepath.read_text(encoding='utf-8')
        assert '---' in content
        assert 'REQ-001' in content
        assert 'Just plain text.' in content

    def test_preserves_other_frontmatter_keys(self, config, input_record, tmp_path):
        """Renumbering preserves all other frontmatter keys."""
        filepath = tmp_path / 'rich.md'
        filepath.write_text(
            "---\nid: OLD\ntitle: Rich Doc\nstatus: active\npriority: 1\n---\nContent.\n",
            encoding='utf-8',
        )

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        extractor.update_artifacts(loc_file, [(artifact, 'REQ-777')])

        content = filepath.read_text(encoding='utf-8')
        assert 'REQ-777' in content
        assert 'title: Rich Doc' in content
        assert 'status: active' in content
        assert 'priority: 1' in content
        assert 'Content.' in content


class TestUpdateArtifactAttributes:
    """Tests for update_artifact_attributes (bulk attr manipulation)."""

    def test_add_attribute(self, config, input_record, tmp_path):
        """Add a new attribute to frontmatter."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\ntitle: Test\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': 'draft'}, 'add')], target_type='attr'
        )

        assert 'status: draft' in result
        assert 'id: REQ-001' in result
        assert 'title: Test' in result

    def test_add_skips_existing(self, config, input_record, tmp_path):
        """Add operation skips attributes that already exist."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\nstatus: active\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': 'draft'}, 'add')], target_type='attr'
        )

        # Should keep 'active', not overwrite with 'draft'
        assert 'status: active' in result
        assert 'draft' not in result

    def test_del_attribute(self, config, input_record, tmp_path):
        """Delete an existing attribute from frontmatter."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\nstatus: active\ntitle: Test\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': None}, 'del')], target_type='attr'
        )

        assert 'status' not in result
        assert 'id: REQ-001' in result
        assert 'title: Test' in result

    def test_del_case_insensitive(self, config, input_record, tmp_path):
        """Delete finds keys case-insensitively."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\nStatus: active\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': None}, 'del')], target_type='attr'
        )

        assert 'Status' not in result
        assert 'status' not in result

    def test_replace_existing(self, config, input_record, tmp_path):
        """Replace an existing attribute value."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\nstatus: draft\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': 'active'}, 'replace')], target_type='attr'
        )

        assert 'status: active' in result
        assert 'draft' not in result

    def test_replace_appends_if_missing(self, config, input_record, tmp_path):
        """Replace adds the attribute if it doesn't exist."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': 'active'}, 'replace')], target_type='attr'
        )

        assert 'status: active' in result
        assert 'id: REQ-001' in result

    def test_replace_with_none_deletes(self, config, input_record, tmp_path):
        """Replace with value=None removes the attribute."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\nstatus: draft\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': None}, 'replace')], target_type='attr'
        )

        assert 'status' not in result

    def test_multiple_attrs_in_one_update(self, config, input_record, tmp_path):
        """Apply multiple attribute changes in a single update."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\nstatus: draft\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file,
            [(artifact, {'status': 'active', 'owner': 'alice'}, 'replace')],
            target_type='attr',
        )

        assert 'status: active' in result
        assert 'owner: alice' in result

    def test_field_target_type_raises(self, config, input_record, tmp_path):
        """target_type='field' raises NotImplementedError."""
        filepath = tmp_path / 'req.md'
        filepath.write_text("---\nid: REQ-001\n---\nBody.\n", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        with pytest.raises(NotImplementedError):
            extractor.update_artifact_attributes(
                loc_file, [(artifact, {'x': 'y'}, 'add')], target_type='field'
            )

    def test_body_preserved(self, config, input_record, tmp_path):
        """Verify markdown body is preserved after attribute manipulation."""
        body = "# Heading\n\nParagraph with **bold**.\n\n- item 1\n- item 2\n"
        filepath = tmp_path / 'req.md'
        filepath.write_text(f"---\nid: REQ-001\n---\n{body}", encoding='utf-8')

        extractor = SimpleMarkdownExtractor(config, input_record)
        blocks = extractor.extract_blocks_from_file(filepath)
        artifact = blocks[0].artifact

        loc_file = config.derive_path(filepath)
        result = extractor.update_artifact_attributes(
            loc_file, [(artifact, {'status': 'TBD'}, 'add')], target_type='attr'
        )

        assert '# Heading' in result
        assert '**bold**' in result
        assert '- item 1' in result
        assert '- item 2' in result
