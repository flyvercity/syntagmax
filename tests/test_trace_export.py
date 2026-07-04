# SPDX-License-Identifier: MIT

import csv
import io
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from syntagmax.artifact import Artifact, ArtifactMap
from syntagmax.errors import FatalError
from syntagmax.plugin import LoadedPlugin, find_plugin_by_name, run_trace_export
from syntagmax.trace import (
    TraceMatrix,
    TraceRecord,
    build_trace_matrix,
    render_trace_csv,
)


# --- Fixtures ---


@pytest.fixture
def mock_config():
    """Minimal Config-like object for tests."""
    config = MagicMock()
    config.params = {'verbose': False}
    return config


def _make_artifact(
    config,
    atype: str,
    aid: str,
    pids: list[str] | None = None,
    children: set[str] | None = None,
    fields: dict | None = None,
):
    """Helper to create a minimal Artifact."""
    a = Artifact(config)
    a.atype = atype
    a.aid = aid
    a.pids = pids or []
    a.children = children or set()
    a.fields = fields or {}
    return a


@pytest.fixture
def simple_artifacts(mock_config) -> ArtifactMap:
    """Simple artifact map with 2 SYS, 3 REQ (one orphan)."""
    sys1 = _make_artifact(mock_config, 'SYS', 'SYS-001', children={'REQ-001', 'REQ-002'}, fields={'title': 'System Req 1'})
    sys2 = _make_artifact(mock_config, 'SYS', 'SYS-002', fields={'title': 'System Req 2'})
    req1 = _make_artifact(mock_config, 'REQ', 'REQ-001', pids=['SYS-001'], fields={'title': 'Child Req 1', 'status': 'active'})
    req2 = _make_artifact(mock_config, 'REQ', 'REQ-002', pids=['SYS-001'], fields={'title': 'Child Req 2', 'status': 'draft'})
    req3 = _make_artifact(mock_config, 'REQ', 'REQ-003', pids=[], fields={'title': 'Orphan Req', 'status': 'active'})

    return {
        'SYS-001': sys1,
        'SYS-002': sys2,
        'REQ-001': req1,
        'REQ-002': req2,
        'REQ-003': req3,
    }


@pytest.fixture
def multi_parent_artifacts(mock_config) -> ArtifactMap:
    """Artifact map where one child has multiple parents."""
    sys1 = _make_artifact(mock_config, 'SYS', 'SYS-001', children={'REQ-001'}, fields={'title': 'Sys 1'})
    sys2 = _make_artifact(mock_config, 'SYS', 'SYS-002', children={'REQ-001'}, fields={'title': 'Sys 2'})
    req1 = _make_artifact(mock_config, 'REQ', 'REQ-001', pids=['SYS-001', 'SYS-002'], fields={'title': 'Multi-parent'})

    return {
        'SYS-001': sys1,
        'SYS-002': sys2,
        'REQ-001': req1,
    }


# --- build_trace_matrix tests ---


class TestBuildTraceMatrix:
    def test_forward_simple(self, simple_artifacts):
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='forward')
        assert matrix.direction == 'forward'
        assert matrix.child_type == 'REQ'
        assert matrix.parent_type == 'SYS'
        # REQ-001 → SYS-001, REQ-002 → SYS-001, REQ-003 → (empty)
        assert len(matrix.records) == 3
        assert matrix.records[0].lead_id == 'REQ-001'
        assert matrix.records[0].linked_id == 'SYS-001'
        assert matrix.records[1].lead_id == 'REQ-002'
        assert matrix.records[1].linked_id == 'SYS-001'
        assert matrix.records[2].lead_id == 'REQ-003'
        assert matrix.records[2].linked_id == ''

    def test_forward_record_numbers_sequential(self, simple_artifacts):
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='forward')
        numbers = [r.record_number for r in matrix.records]
        assert numbers == [1, 2, 3]

    def test_forward_multi_parent(self, multi_parent_artifacts):
        matrix = build_trace_matrix(multi_parent_artifacts, 'REQ', 'SYS', direction='forward')
        # REQ-001 links to SYS-001 and SYS-002 — two rows
        assert len(matrix.records) == 2
        assert matrix.records[0].lead_id == 'REQ-001'
        assert matrix.records[0].linked_id == 'SYS-001'
        assert matrix.records[1].lead_id == 'REQ-001'
        assert matrix.records[1].linked_id == 'SYS-002'

    def test_forward_flat(self, multi_parent_artifacts):
        matrix = build_trace_matrix(multi_parent_artifacts, 'REQ', 'SYS', direction='forward', flat=True)
        assert len(matrix.records) == 1
        assert matrix.records[0].lead_id == 'REQ-001'
        assert matrix.records[0].linked_id == 'SYS-001; SYS-002'

    def test_forward_flat_orphan(self, simple_artifacts):
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='forward', flat=True)
        # REQ-003 has no parents
        orphan_record = [r for r in matrix.records if r.lead_id == 'REQ-003'][0]
        assert orphan_record.linked_id == ''

    def test_reverse_simple(self, simple_artifacts):
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='reverse')
        assert matrix.direction == 'reverse'
        # SYS-001 has children REQ-001, REQ-002; SYS-002 has no children
        assert len(matrix.records) == 3
        assert matrix.records[0].lead_id == 'SYS-001'
        assert matrix.records[0].linked_id == 'REQ-001'
        assert matrix.records[1].lead_id == 'SYS-001'
        assert matrix.records[1].linked_id == 'REQ-002'
        assert matrix.records[2].lead_id == 'SYS-002'
        assert matrix.records[2].linked_id == ''

    def test_reverse_flat(self, simple_artifacts):
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='reverse', flat=True)
        assert len(matrix.records) == 2
        assert matrix.records[0].lead_id == 'SYS-001'
        assert matrix.records[0].linked_id == 'REQ-001; REQ-002'
        assert matrix.records[1].lead_id == 'SYS-002'
        assert matrix.records[1].linked_id == ''

    def test_left_outer_join_orphan(self, simple_artifacts):
        """All lead artifacts appear even without links."""
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='forward')
        lead_ids = [r.lead_id for r in matrix.records]
        assert 'REQ-003' in lead_ids

    def test_left_outer_join_reverse_no_children(self, simple_artifacts):
        """Parent with no children still appears."""
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='reverse')
        lead_ids = [r.lead_id for r in matrix.records]
        assert 'SYS-002' in lead_ids

    def test_attributes_extracted(self, simple_artifacts):
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='forward', attributes=['title', 'status'])
        assert matrix.attribute_names == ['title', 'status']
        rec = matrix.records[0]  # REQ-001
        assert rec.attributes['title'] == 'Child Req 1'
        assert rec.attributes['status'] == 'active'

    def test_missing_attribute_empty_string(self, mock_config):
        """Missing attributes render as empty string."""
        req = _make_artifact(mock_config, 'REQ', 'REQ-001', fields={'title': 'Test'})
        artifacts: ArtifactMap = {'REQ-001': req}
        matrix = build_trace_matrix(artifacts, 'REQ', 'SYS', direction='forward', attributes=['title', 'nonexistent'])
        assert matrix.records[0].attributes['nonexistent'] == ''

    def test_list_attribute_serialization(self, mock_config):
        """List attributes are serialized as semicolon-separated."""
        req = _make_artifact(mock_config, 'REQ', 'REQ-001', fields={'tags': ['safety', 'performance']})
        artifacts: ArtifactMap = {'REQ-001': req}
        matrix = build_trace_matrix(artifacts, 'REQ', 'SYS', direction='forward', attributes=['tags'])
        assert matrix.records[0].attributes['tags'] == 'safety; performance'

    def test_empty_result_no_lead_artifacts(self, mock_config):
        """No artifacts of lead type produces empty matrix."""
        sys1 = _make_artifact(mock_config, 'SYS', 'SYS-001')
        artifacts: ArtifactMap = {'SYS-001': sys1}
        matrix = build_trace_matrix(artifacts, 'REQ', 'SYS', direction='forward')
        assert len(matrix.records) == 0

    def test_excludes_non_matching_types(self, simple_artifacts):
        """Only artifacts of the requested type are included."""
        matrix = build_trace_matrix(simple_artifacts, 'REQ', 'SYS', direction='forward')
        lead_ids = {r.lead_id for r in matrix.records}
        assert 'SYS-001' not in lead_ids
        assert 'SYS-002' not in lead_ids

    def test_unresolved_reference_included(self, mock_config):
        """Parent reference to non-existing artifact is still listed."""
        req = _make_artifact(mock_config, 'REQ', 'REQ-001', pids=['SYS-999'])
        artifacts: ArtifactMap = {'REQ-001': req}
        matrix = build_trace_matrix(artifacts, 'REQ', 'SYS', direction='forward')
        assert matrix.records[0].linked_id == 'SYS-999'


# --- render_trace_csv tests ---


class TestRenderTraceCsv:
    def test_forward_csv_output(self):
        matrix = TraceMatrix(
            direction='forward',
            child_type='REQ',
            parent_type='SYS',
            attribute_names=['title'],
            records=[
                TraceRecord(record_number=1, lead_id='REQ-001', linked_id='SYS-001', attributes={'title': 'Test'}),
                TraceRecord(record_number=2, lead_id='REQ-002', linked_id='', attributes={'title': 'Orphan'}),
            ],
        )
        output = render_trace_csv(matrix)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert rows[0] == ['RecordNumber', 'ChildID', 'ParentID', 'title']
        assert rows[1] == ['1', 'REQ-001', 'SYS-001', 'Test']
        assert rows[2] == ['2', 'REQ-002', '', 'Orphan']

    def test_reverse_csv_output(self):
        matrix = TraceMatrix(
            direction='reverse',
            child_type='REQ',
            parent_type='SYS',
            attribute_names=[],
            records=[
                TraceRecord(record_number=1, lead_id='SYS-001', linked_id='REQ-001', attributes={}),
            ],
        )
        output = render_trace_csv(matrix)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert rows[0] == ['RecordNumber', 'ParentID', 'ChildID']
        assert rows[1] == ['1', 'SYS-001', 'REQ-001']

    def test_tsv_output(self):
        matrix = TraceMatrix(
            direction='forward',
            child_type='REQ',
            parent_type='SYS',
            attribute_names=[],
            records=[
                TraceRecord(record_number=1, lead_id='REQ-001', linked_id='SYS-001', attributes={}),
            ],
        )
        output = render_trace_csv(matrix, delimiter='\t')
        lines = output.strip().split('\n')
        assert '\t' in lines[0]
        assert lines[0].split('\t') == ['RecordNumber', 'ChildID', 'ParentID']
        assert lines[1].split('\t') == ['1', 'REQ-001', 'SYS-001']

    def test_flat_semicolons_in_csv(self):
        matrix = TraceMatrix(
            direction='forward',
            child_type='REQ',
            parent_type='SYS',
            attribute_names=[],
            records=[
                TraceRecord(record_number=1, lead_id='REQ-001', linked_id='SYS-001; SYS-002', attributes={}),
            ],
        )
        output = render_trace_csv(matrix)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert rows[1][2] == 'SYS-001; SYS-002'

    def test_empty_matrix_header_only(self):
        matrix = TraceMatrix(
            direction='forward',
            child_type='REQ',
            parent_type='SYS',
            attribute_names=['title'],
            records=[],
        )
        output = render_trace_csv(matrix)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0] == ['RecordNumber', 'ChildID', 'ParentID', 'title']


# --- Plugin hook tests ---


class TestFindPluginByName:
    def test_finds_existing_plugin(self):
        module = MagicMock(spec=ModuleType)
        plugin = LoadedPlugin(name='my-export', module=module, params={})
        result = find_plugin_by_name([plugin], 'my-export')
        assert result is plugin

    def test_raises_when_not_found(self):
        module = MagicMock(spec=ModuleType)
        plugin = LoadedPlugin(name='other', module=module, params={})
        with pytest.raises(FatalError, match='not found among enabled plugins'):
            find_plugin_by_name([plugin], 'nonexistent')

    def test_raises_when_no_plugins(self):
        with pytest.raises(FatalError, match='No plugins are configured'):
            find_plugin_by_name([], 'any-name')


class TestRunTraceExport:
    def test_calls_export_trace_hook(self, mock_config):
        module = MagicMock(spec=ModuleType)
        module.export_trace = MagicMock()
        plugin = LoadedPlugin(name='test-plugin', module=module, params={'key': 'val'})
        matrix = TraceMatrix(direction='forward', child_type='REQ', parent_type='SYS')

        run_trace_export(plugin, matrix, mock_config)
        module.export_trace.assert_called_once_with(matrix, mock_config, {'key': 'val'})

    def test_raises_when_hook_missing(self, mock_config):
        module = ModuleType('no_hook')
        plugin = LoadedPlugin(name='no-hook', module=module, params={})
        matrix = TraceMatrix(direction='forward', child_type='REQ', parent_type='SYS')

        with pytest.raises(FatalError, match='does not implement the export_trace hook'):
            run_trace_export(plugin, matrix, mock_config)

    def test_wraps_exception_in_fatal_error(self, mock_config):
        module = MagicMock(spec=ModuleType)
        module.export_trace = MagicMock(side_effect=ValueError('test error'))
        plugin = LoadedPlugin(name='broken-plugin', module=module, params={})
        matrix = TraceMatrix(direction='forward', child_type='REQ', parent_type='SYS')

        with pytest.raises(FatalError, match='export_trace raised an exception'):
            run_trace_export(plugin, matrix, mock_config)


# --- CLI Validation tests ---


class TestTraceCliValidation:
    def test_trace_warning_on_invalid_types(self, tmp_path):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        # Create default .syntagmax directory
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        # Write config.toml
        cfg = dot_syntagmax / 'config.toml'
        cfg_content = (
            'base = ".."\n'
            '[[input]]\n'
            'name="rec1"\n'
            'dir="SYS"\n'
            'driver="text"\n'
            'atype="SYS"\n'
            '[metamodel]\n'
            'filename="project.syntagmax"\n'
        )
        cfg.write_text(cfg_content, encoding='utf-8')

        # Write project.syntagmax metamodel
        meta = dot_syntagmax / 'project.syntagmax'
        meta.write_text('artifact SYS:\n    id is string\n    attribute contents is mandatory string\n', encoding='utf-8')

        # Create input dir
        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'trace', '--child', 'INVALID_CHILD', '--parent', 'INVALID_PARENT', '--output', 'console'])
        assert result.exit_code == 0
        assert 'Warning: Child artifact type "INVALID_CHILD" is not defined in the metamodel.' in result.output
        assert 'Warning: Parent artifact type "INVALID_PARENT" is not defined in the metamodel.' in result.output

