# SPDX-License-Identifier: MIT
import pytest

from syntagmax.artifact import LineLocation
from syntagmax.config import Config, InputRecord
from syntagmax.edit_attrs import load_csv_mapping, manipulate_attributes, _get_mandatory_attributes
from syntagmax.errors import FatalError
from syntagmax.extractors.markdown import MarkdownArtifact
from syntagmax.extractors.obsidian import ObsidianExtractor
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
        allow_dirty_worktree=True,
        suppress_tracing=True,
    )


@pytest.fixture
def obsidian_config(params, tmp_path):
    """Create a minimal obsidian config with metamodel.
    NOTE: Files must be created BEFORE this fixture to be discovered.
    Use obsidian_project fixture instead for integration tests.
    """
    metamodel_content = (
        'artifact REQ:\n'
        '    id is string\n'
        '    attribute contents is mandatory string\n'
        '    attribute title is mandatory string\n'
        '    attribute status is mandatory enum [draft, active, retired]\n'
        '    attribute priority is optional enum [critical, high, medium, low]\n'
    )
    metamodel_path = tmp_path / 'project.syntagmax'
    metamodel_path.write_text(metamodel_content, encoding='utf-8')

    cfg_content = (
        'base = "."\n'
        '[[input]]\nname = "requirements"\ndir = "REQ"\ndriver = "obsidian"\natype = "REQ"\n'
        '[metamodel]\nfilename = "project.syntagmax"\n'
    )
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(cfg_content, encoding='utf-8')

    # Create REQ directory
    req_dir = tmp_path / 'REQ'
    req_dir.mkdir()

    return Config(params=params, config_filename=cfg_path)


@pytest.fixture
def sample_req_file(tmp_path):
    """Create a sample requirement markdown file."""
    req_dir = tmp_path / 'REQ'
    req_dir.mkdir(exist_ok=True)
    content = (
        '[REQ]\n'
        'This is a requirement.\n'
        '[id] REQ-001\n'
        '[parent] SYS-001\n'
        '```yaml\n'
        'attrs:\n'
        '  id: REQ-001\n'
        '  title: Sample Requirement\n'
        '  status: draft\n'
        '```\n'
    )
    req_file = req_dir / 'REQ-001.md'
    req_file.write_text(content, encoding='utf-8')
    return req_file


@pytest.fixture
def sample_req_file_no_status(tmp_path):
    """Create a requirement file without status attribute."""
    req_dir = tmp_path / 'REQ'
    req_dir.mkdir(exist_ok=True)
    content = (
        '[REQ]\n'
        'This is a requirement.\n'
        '[id] REQ-002\n'
        '```yaml\n'
        'attrs:\n'
        '  id: REQ-002\n'
        '  title: Another Requirement\n'
        '```\n'
    )
    req_file = req_dir / 'REQ-002.md'
    req_file.write_text(content, encoding='utf-8')
    return req_file


def _make_obsidian_project(params, tmp_path, req_files: dict[str, str]):
    """Helper: create files then Config (so files are discovered by glob)."""
    metamodel_content = (
        'artifact REQ:\n'
        '    id is string\n'
        '    attribute contents is mandatory string\n'
        '    attribute title is mandatory string\n'
        '    attribute status is mandatory enum [draft, active, retired]\n'
        '    attribute priority is optional enum [critical, high, medium, low]\n'
    )
    metamodel_path = tmp_path / 'project.syntagmax'
    metamodel_path.write_text(metamodel_content, encoding='utf-8')

    cfg_content = (
        'base = "."\n'
        '[[input]]\nname = "requirements"\ndir = "REQ"\ndriver = "obsidian"\natype = "REQ"\n'
        '[metamodel]\nfilename = "project.syntagmax"\n'
    )
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(cfg_content, encoding='utf-8')

    req_dir = tmp_path / 'REQ'
    req_dir.mkdir(exist_ok=True)

    created_files = {}
    for filename, content in req_files.items():
        f = req_dir / filename
        f.write_text(content, encoding='utf-8')
        created_files[filename] = f

    config = Config(params=params, config_filename=cfg_path)
    return config, created_files


# ==============================================================================
# CSV Loading Tests
# ==============================================================================


class TestLoadCsvMapping:
    def test_valid_csv(self, tmp_path):
        csv_file = tmp_path / 'mapping.csv'
        csv_file.write_text('id,value\nREQ-001,doors-123\nREQ-002,doors-456\n', encoding='utf-8')

        result = load_csv_mapping(csv_file, 'id', 'value', ',')
        assert result == {'REQ-001': 'doors-123', 'REQ-002': 'doors-456'}

    def test_custom_delimiter(self, tmp_path):
        csv_file = tmp_path / 'mapping.tsv'
        csv_file.write_text('ext_id\tdoors_id\nREQ-001\tD-100\n', encoding='utf-8')

        result = load_csv_mapping(csv_file, 'ext_id', 'doors_id', '\t')
        assert result == {'REQ-001': 'D-100'}

    def test_missing_id_column_raises(self, tmp_path):
        csv_file = tmp_path / 'mapping.csv'
        csv_file.write_text('name,value\nREQ-001,val\n', encoding='utf-8')

        with pytest.raises(FatalError, match='CSV column "id" not found'):
            load_csv_mapping(csv_file, 'id', 'value', ',')

    def test_missing_value_column_raises(self, tmp_path):
        csv_file = tmp_path / 'mapping.csv'
        csv_file.write_text('id,name\nREQ-001,val\n', encoding='utf-8')

        with pytest.raises(FatalError, match='CSV column "value" not found'):
            load_csv_mapping(csv_file, 'id', 'value', ',')

    def test_empty_csv_returns_empty(self, tmp_path):
        csv_file = tmp_path / 'mapping.csv'
        csv_file.write_text('id,value\n', encoding='utf-8')

        result = load_csv_mapping(csv_file, 'id', 'value', ',')
        assert result == {}

    def test_duplicate_ids_last_wins(self, tmp_path):
        csv_file = tmp_path / 'mapping.csv'
        csv_file.write_text('id,value\nREQ-001,first\nREQ-001,second\n', encoding='utf-8')

        result = load_csv_mapping(csv_file, 'id', 'value', ',')
        assert result == {'REQ-001': 'second'}

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FatalError, match='CSV file not found'):
            load_csv_mapping(tmp_path / 'missing.csv', 'id', 'value', ',')

    def test_utf8_bom_handled(self, tmp_path):
        csv_file = tmp_path / 'mapping.csv'
        csv_file.write_bytes(b'\xef\xbb\xbfid,value\nREQ-001,val\n')

        result = load_csv_mapping(csv_file, 'id', 'value', ',')
        assert result == {'REQ-001': 'val'}


# ==============================================================================
# Metamodel Attribute Lookup Tests
# ==============================================================================


class TestGetMandatoryAttributes:
    def test_finds_mandatory_attrs(self):
        metamodel = {
            'artifacts': {
                'REQ': {
                    'attributes': {
                        'id': [{'presence': 'mandatory'}],
                        'contents': [{'presence': 'mandatory'}],
                        'title': [{'presence': 'mandatory', 'condition': None}],
                        'status': [{'presence': 'mandatory', 'condition': None}],
                        'priority': [{'presence': 'optional'}],
                    }
                }
            }
        }
        result = _get_mandatory_attributes(metamodel, 'REQ')
        assert 'title' in result
        assert 'status' in result
        assert 'id' not in result  # excluded
        assert 'contents' not in result  # excluded
        assert 'priority' not in result  # optional

    def test_conditional_mandatory_excluded(self):
        metamodel = {
            'artifacts': {
                'REQ': {
                    'attributes': {
                        'justification': [{'presence': 'mandatory', 'condition': 'if derived'}],
                    }
                }
            }
        }
        result = _get_mandatory_attributes(metamodel, 'REQ')
        assert 'justification' not in result

    def test_unknown_atype_returns_empty(self):
        metamodel = {'artifacts': {'SYS': {'attributes': {}}}}
        result = _get_mandatory_attributes(metamodel, 'REQ')
        assert result == []


# ==============================================================================
# Extractor-Level Tests (update_artifact_attributes)
# ==============================================================================


class TestMarkdownExtractorUpdateAttributes:
    @pytest.fixture
    def setup_extractor(self, params, tmp_path):
        """Create config + extractor for testing."""
        cfg_content = (
            'base = "."\n'
            '[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\n'
        )
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(cfg_content, encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)

        record = InputRecord(
            name='test',
            dir='.',
            record_base=tmp_path,
            filepaths=[],
            driver='obsidian',
            default_atype='REQ',
            marker='REQ',
        )
        extractor = ObsidianExtractor(config, record)
        return config, extractor, tmp_path

    def test_yaml_add_new_attr(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = (
            '[REQ]\nBody text\n[id] REQ-001\n'
            '```yaml\nattrs:\n  id: REQ-001\n  title: Test\n```\n'
        )
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        # Create a mock artifact with location
        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 8))
        from benedict import benedict
        artifact.yaml_data = benedict({'attrs': {'id': 'REQ-001', 'title': 'Test'}})

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'status': 'draft'}, 'add')], 'attr'
        )
        assert 'status: draft' in result
        assert 'title: Test' in result

    def test_yaml_add_skips_existing(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = (
            '[REQ]\nBody text\n[id] REQ-001\n'
            '```yaml\nattrs:\n  id: REQ-001\n  status: active\n```\n'
        )
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 8))
        from benedict import benedict
        artifact.yaml_data = benedict({'attrs': {'id': 'REQ-001', 'status': 'active'}})

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'status': 'draft'}, 'add')], 'attr'
        )
        # Status should remain 'active', not changed to 'draft'
        assert 'status: active' in result
        assert 'status: draft' not in result

    def test_yaml_del_removes_attr(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = (
            '[REQ]\nBody text\n[id] REQ-001\n'
            '```yaml\nattrs:\n  id: REQ-001\n  status: draft\n  title: Test\n```\n'
        )
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 9))
        from benedict import benedict
        artifact.yaml_data = benedict({'attrs': {'id': 'REQ-001', 'status': 'draft', 'title': 'Test'}})

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'status': None}, 'del')], 'attr'
        )
        assert 'status' not in result
        assert 'title: Test' in result

    def test_yaml_replace_updates_existing(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = (
            '[REQ]\nBody text\n[id] REQ-001\n'
            '```yaml\nattrs:\n  id: REQ-001\n  status: draft\n```\n'
        )
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 8))
        from benedict import benedict
        artifact.yaml_data = benedict({'attrs': {'id': 'REQ-001', 'status': 'draft'}})

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'status': 'active'}, 'replace')], 'attr'
        )
        assert 'status: active' in result
        assert 'status: draft' not in result

    def test_yaml_replace_adds_if_missing(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = (
            '[REQ]\nBody text\n[id] REQ-001\n'
            '```yaml\nattrs:\n  id: REQ-001\n```\n'
        )
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 7))
        from benedict import benedict
        artifact.yaml_data = benedict({'attrs': {'id': 'REQ-001'}})

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'status': 'active'}, 'replace')], 'attr'
        )
        assert 'status: active' in result

    def test_inline_field_add(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = '[REQ]\nBody text\n[id] REQ-001\n[/REQ]\n'
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 4))
        artifact.yaml_data = None
        artifact.source_metadata = {}

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'priority': 'high'}, 'add')], 'field'
        )
        assert '[priority] high' in result
        # Should be before [/REQ]
        assert result.index('[priority] high') < result.index('[/REQ]')

    def test_inline_field_del(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = '[REQ]\nBody text\n[id] REQ-001\n[priority] high\n[/REQ]\n'
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 5))
        artifact.yaml_data = None
        artifact.source_metadata = {'priority': 'markdown'}

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'priority': None}, 'del')], 'field'
        )
        assert '[priority]' not in result
        assert '[id] REQ-001' in result

    def test_inline_field_replace_in_place(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = '[REQ]\nBody text\n[id] REQ-001\n[priority] low\n[status] draft\n[/REQ]\n'
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 6))
        artifact.yaml_data = None
        artifact.source_metadata = {'priority': 'markdown', 'status': 'markdown'}

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'priority': 'critical'}, 'replace')], 'field'
        )
        assert '[priority] critical' in result
        # Should preserve order: priority before status
        assert result.index('[priority] critical') < result.index('[status] draft')

    def test_line_ending_preservation_crlf(self, setup_extractor):
        config, extractor, tmp_path = setup_extractor
        content = '[REQ]\r\nBody text\r\n[id] REQ-001\r\n```yaml\r\nattrs:\r\n  id: REQ-001\r\n```\r\n'
        req_file = tmp_path / 'test.md'
        req_file.write_bytes(content.encode('utf-8'))

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 7))
        from benedict import benedict
        artifact.yaml_data = benedict({'attrs': {'id': 'REQ-001'}})

        result = extractor.update_artifact_attributes(
            'test.md', [(artifact, {'status': 'draft'}, 'add')], 'attr'
        )
        # The newly inserted YAML block should use \r\n
        assert 'status: draft\r\n' in result
        assert '\n' not in result.replace('\r\n', '')
    def test_yaml_comment_warning(self, setup_extractor, caplog):
        """Test that YAML blocks with comments are preserved (no longer lost)."""
        import logging
        config, extractor, tmp_path = setup_extractor
        content = (
            '[REQ]\nBody text\n[id] REQ-001\n'
            '```yaml\n# This is a comment\nattrs:\n  id: REQ-001\n```\n'
        )
        req_file = tmp_path / 'test.md'
        req_file.write_text(content, encoding='utf-8')

        artifact = MarkdownArtifact(config)
        artifact.location = LineLocation('test.md', (1, 8))
        from benedict import benedict
        artifact.yaml_data = benedict({'attrs': {'id': 'REQ-001'}})

        with caplog.at_level(logging.WARNING, logger='syntagmax.extractors.markdown'):
            result = extractor.update_artifact_attributes(
                'test.md', [(artifact, {'status': 'draft'}, 'add')], 'attr'
            )
        # Comments are now preserved by round-trip editing
        assert '# This is a comment' in result
        assert 'status: draft' in result
        # No warning about comment loss should be emitted
        assert not any('comment' in r.message.lower() for r in caplog.records)


# ==============================================================================
# Integration Tests (manipulate_attributes orchestration)
# ==============================================================================


class TestManipulateAttributes:
    REQ_WITH_STATUS = (
        '[REQ]\n'
        'This is a requirement.\n'
        '[id] REQ-001\n'
        '[parent] SYS-001\n'
        '```yaml\n'
        'attrs:\n'
        '  id: REQ-001\n'
        '  title: Sample Requirement\n'
        '  status: draft\n'
        '```\n'
    )

    REQ_NO_STATUS = (
        '[REQ]\n'
        'This is a requirement.\n'
        '[id] REQ-002\n'
        '```yaml\n'
        'attrs:\n'
        '  id: REQ-002\n'
        '  title: Another Requirement\n'
        '```\n'
    )

    def test_add_attribute_to_artifacts(self, params, tmp_path):
        """Test adding an attribute that doesn't exist yet."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-002.md': self.REQ_NO_STATUS})
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='add',
            target_type='attr',
            name='priority',
            value='medium',
            csv_mapping=None,
            dry_run=False,
        )
        content = files['REQ-002.md'].read_text(encoding='utf-8')
        assert 'priority' in content

    def test_add_skips_existing_attribute(self, params, tmp_path):
        """Test that add doesn't overwrite an existing attribute."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-001.md': self.REQ_WITH_STATUS})
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='add',
            target_type='attr',
            name='status',
            value='active',
            csv_mapping=None,
            dry_run=False,
        )
        content = files['REQ-001.md'].read_text(encoding='utf-8')
        # Original value should be preserved
        assert 'status: draft' in content

    def test_add_defaults_to_tbd(self, params, tmp_path):
        """Test that add uses TBD when no value specified."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-002.md': self.REQ_NO_STATUS})
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='add',
            target_type='attr',
            name='priority',
            value=None,
            csv_mapping=None,
            dry_run=False,
        )
        content = files['REQ-002.md'].read_text(encoding='utf-8')
        assert 'priority: TBD' in content

    def test_del_removes_attribute(self, params, tmp_path):
        """Test deleting an existing attribute."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-001.md': self.REQ_WITH_STATUS})
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='del',
            target_type='attr',
            name='status',
            value=None,
            csv_mapping=None,
            dry_run=False,
        )
        content = files['REQ-001.md'].read_text(encoding='utf-8')
        assert 'status' not in content

    def test_replace_updates_existing(self, params, tmp_path):
        """Test replacing an existing attribute value."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-001.md': self.REQ_WITH_STATUS})
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='replace',
            target_type='attr',
            name='status',
            value='active',
            csv_mapping=None,
            dry_run=False,
        )
        content = files['REQ-001.md'].read_text(encoding='utf-8')
        assert 'status: active' in content
        assert 'status: draft' not in content

    def test_dry_run_no_file_changes(self, params, tmp_path):
        """Test that dry-run doesn't modify files."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-002.md': self.REQ_NO_STATUS})
        original_content = files['REQ-002.md'].read_text(encoding='utf-8')

        manipulate_attributes(
            config=config,
            section='requirements',
            operation='add',
            target_type='attr',
            name='priority',
            value='high',
            csv_mapping=None,
            dry_run=True,
        )

        assert files['REQ-002.md'].read_text(encoding='utf-8') == original_content

    def test_csv_mapping_applies_values(self, params, tmp_path):
        """Test CSV mapping provides per-artifact values."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-001.md': self.REQ_WITH_STATUS})
        csv_mapping = {'REQ-001': 'doors-123'}
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='replace',
            target_type='attr',
            name='doors_id',
            value=None,
            csv_mapping=csv_mapping,
            dry_run=False,
        )
        content = files['REQ-001.md'].read_text(encoding='utf-8')
        assert 'doors_id: doors-123' in content

    def test_csv_fallback_to_literal_value(self, params, tmp_path):
        """Test that --value is used as fallback when ID not in CSV."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-002.md': self.REQ_NO_STATUS})
        csv_mapping = {'REQ-999': 'some-val'}  # Doesn't match REQ-002
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='replace',
            target_type='attr',
            name='doors_id',
            value='UNKNOWN',
            csv_mapping=csv_mapping,
            dry_run=False,
        )
        content = files['REQ-002.md'].read_text(encoding='utf-8')
        assert 'doors_id: UNKNOWN' in content

    def test_non_obsidian_driver_raises(self, params, tmp_path):
        """Test that non-obsidian drivers raise an error."""
        cfg_content = (
            'base = "."\n'
            '[[input]]\nname = "src"\ndir = "."\ndriver = "text"\natype = "SRC"\n'
        )
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(cfg_content, encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)

        with pytest.raises(FatalError, match='Only the "obsidian" driver is supported'):
            manipulate_attributes(
                config=config,
                section='src',
                operation='add',
                target_type='attr',
                name='status',
                value='draft',
                csv_mapping=None,
                dry_run=False,
            )

    def test_nonexistent_section_raises(self, params, tmp_path):
        """Test that a nonexistent section raises an error."""
        config, _ = _make_obsidian_project(params, tmp_path, {})
        with pytest.raises(FatalError, match='not found in configuration'):
            manipulate_attributes(
                config=config,
                section='nonexistent',
                operation='add',
                target_type='attr',
                name='status',
                value='draft',
                csv_mapping=None,
                dry_run=False,
            )

    def test_metamodel_driven_add(self, params, tmp_path):
        """Test that omitting --name adds all mandatory metamodel attributes."""
        config, files = _make_obsidian_project(params, tmp_path, {'REQ-002.md': self.REQ_NO_STATUS})
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='add',
            target_type='attr',
            name=None,
            value=None,
            csv_mapping=None,
            dry_run=False,
        )
        content = files['REQ-002.md'].read_text(encoding='utf-8')
        # title already exists, should not be overwritten
        assert 'title: Another Requirement' in content
        # status is mandatory and missing, should be added as TBD
        assert 'status: TBD' in content

    def test_metamodel_driven_add_no_metamodel_raises(self, params, tmp_path):
        """Test that metamodel-driven add without metamodel raises error."""
        cfg_content = (
            'base = "."\n'
            '[[input]]\nname = "reqs"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\n'
        )
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(cfg_content, encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)

        with pytest.raises(FatalError, match='Cannot add mandatory attributes without a metamodel'):
            manipulate_attributes(
                config=config,
                section='reqs',
                operation='add',
                target_type='attr',
                name=None,
                value=None,
                csv_mapping=None,
                dry_run=False,
            )

    def test_multi_attribute_update_on_same_artifact_no_corruption(self, params, tmp_path):
        """Test that updating multiple attributes on the same artifact groups updates and avoids corruption."""
        req_content = (
            '[REQ]\n'
            'Body text\n'
            '[id] REQ-001\n'
            '[/REQ]\n'
            '[REQ]\n'
            'Other artifact\n'
            '[id] REQ-002\n'
            '[/REQ]\n'
        )
        config, files = _make_obsidian_project(
            params, tmp_path, {'REQ-001.md': req_content}
        )
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='add',
            target_type='field',
            name=None,  # metamodel-driven: will add title and status
            value=None,
            csv_mapping=None,
            dry_run=False,
        )
        content = files['REQ-001.md'].read_text(encoding='utf-8')
        assert '[title] TBD' in content
        assert '[status] TBD' in content
        assert '[id] REQ-002' in content
        assert 'Other artifact' in content

    def test_csv_fallback_skips_unmatched_on_add(self, params, tmp_path):
        """Test that add operation skips unmatched artifacts in CSV when no fallback value is provided."""
        config, files = _make_obsidian_project(
            params, tmp_path, {'REQ-002.md': self.REQ_NO_STATUS}
        )
        csv_mapping = {'REQ-999': 'active'}  # REQ-002 is not matched
        manipulate_attributes(
            config=config,
            section='requirements',
            operation='add',
            target_type='attr',
            name='status',
            value=None,  # No literal fallback
            csv_mapping=csv_mapping,
            dry_run=False,
        )
        content = files['REQ-002.md'].read_text(encoding='utf-8')
        assert 'status' not in content

