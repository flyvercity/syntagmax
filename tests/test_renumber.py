# SPDX-License-Identifier: MIT
"""Tests for the refactored renumber_artifacts two-pass algorithm."""

import logging
import textwrap

import pytest

from syntagmax.config import Config
from syntagmax.edit import renumber_artifacts
from syntagmax.params import Params


@pytest.fixture
def params():
    return Params(
        log_level='info',
        render_tree=False,
        ai=False,
        cwd='.',
        no_git=True,
        allow_dirty_worktree=True,
        suppress_tracing=True,
        tasks=False,
        language='en',
    )


def _make_project(tmp_path, params, metamodel_text, config_text, files):
    """Create a project directory with config, metamodel, and requirement files."""
    project_dir = tmp_path / 'project'
    project_dir.mkdir()

    metamodel_path = project_dir / 'project.syntagmax'
    metamodel_path.write_text(metamodel_text, encoding='utf-8')

    config_path = project_dir / 'config.toml'
    config_path.write_text(config_text, encoding='utf-8')

    req_dir = project_dir / 'REQ'
    req_dir.mkdir()

    for filename, content in files.items():
        filepath = req_dir / filename
        filepath.write_text(content, encoding='utf-8')

    config = Config(params=params, config_filename=config_path)
    return config, project_dir


def _make_multi_type_project(tmp_path, params, metamodel_text, config_text, req_files, sys_files):
    """Create a project with both REQ and SYS directories."""
    project_dir = tmp_path / 'project'
    project_dir.mkdir()

    metamodel_path = project_dir / 'project.syntagmax'
    metamodel_path.write_text(metamodel_text, encoding='utf-8')

    config_path = project_dir / 'config.toml'
    config_path.write_text(config_text, encoding='utf-8')

    req_dir = project_dir / 'REQ'
    req_dir.mkdir()
    for filename, content in req_files.items():
        filepath = req_dir / filename
        filepath.write_text(content, encoding='utf-8')

    sys_dir = project_dir / 'SYS'
    sys_dir.mkdir()
    for filename, content in sys_files.items():
        filepath = sys_dir / filename
        filepath.write_text(content, encoding='utf-8')

    config = Config(params=params, config_filename=config_path)
    return config, project_dir


METAMODEL_WITH_SCHEMA = textwrap.dedent("""\
    artifact REQ:
        id is string as REQ-{num:3}
        attribute contents is mandatory string
        attribute title is mandatory string
""")

METAMODEL_WITHOUT_SCHEMA = textwrap.dedent("""\
    artifact REQ:
        id is string
        attribute contents is mandatory string
        attribute title is mandatory string
""")

CONFIG_BASE = textwrap.dedent("""\
    base = "."

    [[input]]
    name = "requirements"
    dir = "REQ"
    driver = "obsidian"
    atype = "REQ"

    [metamodel]
    filename = "project.syntagmax"
""")

CONFIG_MULTI_TYPE = textwrap.dedent("""\
    base = "."

    [[input]]
    name = "requirements"
    dir = "REQ"
    driver = "obsidian"
    atype = "REQ"

    [[input]]
    name = "system"
    dir = "SYS"
    driver = "obsidian"
    atype = "SYS"

    [metamodel]
    filename = "project.syntagmax"
""")


def _read_file(project_dir, dirname, filename):
    """Read a file from the project directory."""
    return (project_dir / dirname / filename).read_text(encoding='utf-8')


def _req(aid=None, title='A Requirement'):
    """Helper: build an obsidian requirement file content string."""
    lines = ['[REQ]', 'Requirement content.', '```yaml', 'attrs:']
    if aid is not None:
        lines.append(f'    id: {aid}')
    lines.append(f'    title: {title}')
    lines.append('```')
    lines.append('')  # trailing newline
    return '\n'.join(lines)


def _sys(aid=None, title='A System Req'):
    """Helper: build an obsidian SYS requirement file content string."""
    lines = ['[SYS]', 'System content.', '```yaml', 'attrs:']
    if aid is not None:
        lines.append(f'    id: {aid}')
    lines.append(f'    title: {title}')
    lines.append('```')
    lines.append('')
    return '\n'.join(lines)


class TestMaxPlusOneBehaviour:
    """Max+1 behaviour: valid REQ-002, REQ-005, REQ-003 + two <undefined> → get REQ-006, REQ-007."""

    def test_undefined_get_max_plus_one(self, tmp_path, params):
        files = {
            'a-req-002.md': _req('REQ-002', 'Req A'),
            'b-req-005.md': _req('REQ-005', 'Req B'),
            'c-req-003.md': _req('REQ-003', 'Req C'),
            'd-undefined-1.md': _req(None, 'Req D'),
            'e-undefined-2.md': _req(None, 'Req E'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)
        renumber_artifacts(config, dry_run=False)

        # Valid IDs should be preserved
        content_a = _read_file(project_dir, 'REQ', 'a-req-002.md')
        assert 'id: REQ-002' in content_a

        content_b = _read_file(project_dir, 'REQ', 'b-req-005.md')
        assert 'id: REQ-005' in content_b

        content_c = _read_file(project_dir, 'REQ', 'c-req-003.md')
        assert 'id: REQ-003' in content_c

        # Undefined should get REQ-006, REQ-007 (sorted by location: d < e)
        content_d = _read_file(project_dir, 'REQ', 'd-undefined-1.md')
        assert 'id: REQ-006' in content_d

        content_e = _read_file(project_dir, 'REQ', 'e-undefined-2.md')
        assert 'id: REQ-007' in content_e


class TestForceMode:
    """Force mode: same input → all get REQ-001 through REQ-005."""

    def test_force_renumbers_all(self, tmp_path, params):
        files = {
            'a-req-002.md': _req('REQ-002', 'Req A'),
            'b-req-005.md': _req('REQ-005', 'Req B'),
            'c-req-003.md': _req('REQ-003', 'Req C'),
            'd-undefined-1.md': _req(None, 'Req D'),
            'e-undefined-2.md': _req(None, 'Req E'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)
        renumber_artifacts(config, force=True)

        # All should get sequential IDs from 1 (sorted by location: a, b, c, d, e)
        content_a = _read_file(project_dir, 'REQ', 'a-req-002.md')
        assert 'id: REQ-001' in content_a

        content_b = _read_file(project_dir, 'REQ', 'b-req-005.md')
        assert 'id: REQ-002' in content_b

        content_c = _read_file(project_dir, 'REQ', 'c-req-003.md')
        assert 'id: REQ-003' in content_c

        content_d = _read_file(project_dir, 'REQ', 'd-undefined-1.md')
        assert 'id: REQ-004' in content_d

        content_e = _read_file(project_dir, 'REQ', 'e-undefined-2.md')
        assert 'id: REQ-005' in content_e


class TestAllValidNoForce:
    """All valid (no force): no modifications."""

    def test_no_changes_when_all_valid(self, tmp_path, params):
        files = {
            'a-req-001.md': _req('REQ-001', 'Req A'),
            'b-req-002.md': _req('REQ-002', 'Req B'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)
        renumber_artifacts(config, dry_run=False)

        # Contents should be unchanged
        content_a = _read_file(project_dir, 'REQ', 'a-req-001.md')
        assert 'id: REQ-001' in content_a

        content_b = _read_file(project_dir, 'REQ', 'b-req-002.md')
        assert 'id: REQ-002' in content_b


class TestAllInvalid:
    """All invalid: counter starts at 1."""

    def test_all_undefined_start_at_1(self, tmp_path, params):
        files = {
            'a-first.md': _req(None, 'Req A'),
            'b-second.md': _req(None, 'Req B'),
            'c-third.md': _req(None, 'Req C'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)
        renumber_artifacts(config, dry_run=False)

        content_a = _read_file(project_dir, 'REQ', 'a-first.md')
        assert 'id: REQ-001' in content_a

        content_b = _read_file(project_dir, 'REQ', 'b-second.md')
        assert 'id: REQ-002' in content_b

        content_c = _read_file(project_dir, 'REQ', 'c-third.md')
        assert 'id: REQ-003' in content_c


class TestTemplateIdsRenumbered:
    """Template IDs (containing macros) are treated as needing renumbering."""

    def test_template_id_gets_renumbered(self, tmp_path, params):
        files = {
            'a-valid.md': _req('REQ-001', 'Req A'),
            'b-template.md': _req('REQ-{num:3}', 'Req B'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)
        renumber_artifacts(config, dry_run=False)

        # Valid ID preserved
        content_a = _read_file(project_dir, 'REQ', 'a-valid.md')
        assert 'id: REQ-001' in content_a

        # Template gets max+1 = 002
        content_b = _read_file(project_dir, 'REQ', 'b-template.md')
        assert 'id: REQ-002' in content_b


class TestNoSchemaInMetamodel:
    """No schema in metamodel: falls back to {atype}-{num:3}, all renumbered from 1."""

    def test_default_schema_used(self, tmp_path, params):
        files = {
            'a-first.md': _req(None, 'Req A'),
            'b-second.md': _req(None, 'Req B'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITHOUT_SCHEMA, CONFIG_BASE, files)
        renumber_artifacts(config, dry_run=False)

        content_a = _read_file(project_dir, 'REQ', 'a-first.md')
        assert 'id: REQ-001' in content_a

        content_b = _read_file(project_dir, 'REQ', 'b-second.md')
        assert 'id: REQ-002' in content_b


class TestPerTypeIsolation:
    """Per-type isolation: REQ and SYS numbering are independent."""

    def test_types_numbered_independently(self, tmp_path, params):
        metamodel = textwrap.dedent("""\
            artifact REQ:
                id is string as REQ-{num:3}
                attribute contents is mandatory string
                attribute title is mandatory string

            artifact SYS:
                id is string as SYS-{num:3}
                attribute contents is mandatory string
                attribute title is mandatory string
        """)

        req_files = {
            'a-req-003.md': _req('REQ-003', 'Req A'),
            'b-undefined.md': _req(None, 'Req B'),
        }

        sys_files = {
            'a-sys-010.md': _sys('SYS-010', 'Sys A'),
            'b-undefined.md': _sys(None, 'Sys B'),
        }

        config, project_dir = _make_multi_type_project(
            tmp_path, params, metamodel, CONFIG_MULTI_TYPE, req_files, sys_files
        )
        renumber_artifacts(config, dry_run=False)

        # REQ gets max(3)+1 = 4
        content_req_a = _read_file(project_dir, 'REQ', 'a-req-003.md')
        assert 'id: REQ-003' in content_req_a

        content_req_b = _read_file(project_dir, 'REQ', 'b-undefined.md')
        assert 'id: REQ-004' in content_req_b

        # SYS gets max(10)+1 = 11
        content_sys_a = _read_file(project_dir, 'SYS', 'a-sys-010.md')
        assert 'id: SYS-010' in content_sys_a

        content_sys_b = _read_file(project_dir, 'SYS', 'b-undefined.md')
        assert 'id: SYS-011' in content_sys_b


class TestMultipleNumInTemplate:
    """Multiple {num} in template: fails before changes."""

    def test_multiple_num_macros_aborts(self, tmp_path, params, caplog):
        # Use a template ID that has multiple {num} macros — must be quoted for YAML
        files = {
            'a-bad-template.md': '[REQ]\nRequirement content.\n```yaml\nattrs:\n    id: "{num}-{num:2}"\n    title: Req A\n```\n',
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITHOUT_SCHEMA, CONFIG_BASE, files)

        with caplog.at_level(logging.ERROR):
            renumber_artifacts(config, dry_run=False)

        assert 'multiple {num} macros' in caplog.text


class TestZeroNumInSchema:
    """Zero {num} in schema: artifact is skipped (not renumbered)."""

    def test_no_num_in_schema_skipped(self, tmp_path, params):
        metamodel = textwrap.dedent("""\
            artifact REQ:
                id is string as REQ-FIXED
                attribute contents is mandatory string
                attribute title is mandatory string
        """)

        files = {
            'a-first.md': _req('REQ-FIXED', 'Req A'),
            'b-second.md': _req('SOMETHING', 'Req B'),
        }

        config, project_dir = _make_project(tmp_path, params, metamodel, CONFIG_BASE, files)
        renumber_artifacts(config, dry_run=False)

        # Nothing should change — schema has no {num}
        content_a = _read_file(project_dir, 'REQ', 'a-first.md')
        assert 'id: REQ-FIXED' in content_a

        content_b = _read_file(project_dir, 'REQ', 'b-second.md')
        assert 'id: SOMETHING' in content_b


class TestDuplicateValidIds:
    """Duplicate valid IDs: both preserved, warning logged."""

    def test_duplicates_preserved_with_warning(self, tmp_path, params, caplog):
        files = {
            'a-dup-1.md': _req('REQ-001', 'Req A'),
            'b-dup-2.md': _req('REQ-001', 'Req B'),
            'c-undefined.md': _req(None, 'Req C'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)

        with caplog.at_level(logging.WARNING):
            renumber_artifacts(config, dry_run=False)

        # Both duplicates preserved
        content_a = _read_file(project_dir, 'REQ', 'a-dup-1.md')
        assert 'id: REQ-001' in content_a

        content_b = _read_file(project_dir, 'REQ', 'b-dup-2.md')
        assert 'id: REQ-001' in content_b

        # Undefined gets max(1)+1 = 2
        content_c = _read_file(project_dir, 'REQ', 'c-undefined.md')
        assert 'id: REQ-002' in content_c

        # Warning about duplicates
        assert 'Duplicate valid IDs' in caplog.text
        assert 'REQ-001' in caplog.text


class TestPadding:
    """Padding: max=999, next=REQ-1000 (doesn't truncate)."""

    def test_padding_does_not_truncate(self, tmp_path, params):
        files = {
            'a-req-999.md': _req('REQ-999', 'Req A'),
            'b-undefined.md': _req(None, 'Req B'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)
        renumber_artifacts(config, dry_run=False)

        # REQ-999 preserved
        content_a = _read_file(project_dir, 'REQ', 'a-req-999.md')
        assert 'id: REQ-999' in content_a

        # Next gets REQ-1000 (4 digits even though schema says 3)
        content_b = _read_file(project_dir, 'REQ', 'b-undefined.md')
        assert 'id: REQ-1000' in content_b


class TestDryRun:
    """Dry run: logs changes but doesn't modify files."""

    def test_dry_run_no_file_changes(self, tmp_path, params, caplog):
        files = {
            'a-undefined.md': _req(None, 'Req A'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)

        with caplog.at_level(logging.INFO):
            renumber_artifacts(config, dry_run=True)

        # File should NOT be modified
        content_a = _read_file(project_dir, 'REQ', 'a-undefined.md')
        assert 'id: REQ-001' not in content_a

        # But log should mention the planned change
        assert 'DRY-RUN' in caplog.text
        assert 'REQ-001' in caplog.text


class TestSummaryLogging:
    """Verify summary is logged."""

    def test_summary_logged(self, tmp_path, params, caplog):
        files = {
            'a-valid.md': _req('REQ-001', 'Req A'),
            'b-undefined.md': _req(None, 'Req B'),
        }

        config, project_dir = _make_project(tmp_path, params, METAMODEL_WITH_SCHEMA, CONFIG_BASE, files)

        with caplog.at_level(logging.INFO):
            renumber_artifacts(config, dry_run=True)

        assert 'Preserved 1 valid IDs' in caplog.text
        assert 'Renumbered 1 artifacts' in caplog.text
        assert 'Total: 2' in caplog.text
