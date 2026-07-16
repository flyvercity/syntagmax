# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-15
# Description: Unit and integration tests for change report summary mode.

import git
import pytest
from click.testing import CliRunner

from syntagmax.change_diff import (
    ArtifactChange,
    ArtifactDiff,
    FileDiff,
    FileStatus,
    TextBlockDiff,
    TextFragmentChange,
)
from syntagmax.change_render import (
    ChangeReportData,
    ExtractionError,
    render_summary_report,
    _format_line_range,
    _format_text_fragment_entry,
    _group_artifacts_by_file,
    _group_text_fragments_by_file,
    _format_field_value,
    _blockquote_content,
    _build_objects_by_file,
    _normalize_binary_status,
    _render_changed_files,
)
from syntagmax.cli import rms


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestFormatLineRange:
    """Tests for _format_line_range helper."""

    def test_single_line(self):
        assert _format_line_range(45, 45) == 'lines 45'

    def test_multi_line(self):
        assert _format_line_range(45, 52) == 'lines 45\u201352'

    def test_start_one(self):
        assert _format_line_range(1, 10) == 'lines 1\u201310'

    def test_large_range(self):
        assert _format_line_range(100, 500) == 'lines 100\u2013500'


class TestFormatFieldValue:
    """Tests for _format_field_value helper."""

    def test_none_returns_dash(self):
        assert _format_field_value(None) == '—'

    def test_simple_string(self):
        assert _format_field_value('simple') == 'simple'

    def test_multiline_truncates(self):
        assert _format_field_value('line1\nline2') == 'line1 …'

    def test_list_joined(self):
        assert _format_field_value(['a', 'b']) == 'a, b'

    def test_multiline_with_bullets(self):
        assert _format_field_value('first\n- bullet\n- bullet') == 'first …'

    def test_empty_first_line_skipped(self):
        assert _format_field_value('\n\nreal') == 'real …'

    def test_pipe_escaped(self):
        assert _format_field_value('a | b') == 'a \\| b'

    def test_list_with_multiline_element(self):
        assert _format_field_value(['line1\nline2', 'ok']) == 'line1 …, ok'

    def test_integer_value(self):
        assert _format_field_value(42) == '42'

    def test_list_with_pipe(self):
        assert _format_field_value(['a|b', 'c']) == 'a\\|b, c'

    def test_angle_brackets_backticked(self):
        assert _format_field_value('<undefined>') == '`<undefined>`'

    def test_no_backticks_without_both_brackets(self):
        assert _format_field_value('a < b') == 'a < b'


class TestBlockquoteContent:
    """Tests for _blockquote_content helper."""

    def test_plain_text(self):
        result = _blockquote_content('hello\nworld')
        assert result == ['> hello', '> world']

    def test_header_escaped(self):
        result = _blockquote_content('# Header')
        assert result == ['> \\# Header']

    def test_h2_escaped(self):
        result = _blockquote_content('## Sub')
        assert result == ['> \\## Sub']

    def test_empty_string(self):
        result = _blockquote_content('')
        assert result == []

    def test_whitespace_only(self):
        result = _blockquote_content('   ')
        assert result == []

    def test_leading_whitespace_before_hash(self):
        result = _blockquote_content('  # indented header')
        assert result == ['>   \\# indented header']

    def test_hash_inside_code_block_not_escaped(self):
        text = '```python\n# comment\nprint("hi")\n```'
        result = _blockquote_content(text)
        assert result == [
            '> ```python',
            '> # comment',
            '> print("hi")',
            '> ```',
        ]

    def test_multiple_code_blocks_toggle(self):
        text = '# Title\n```\n# not escaped\n```\n# Escaped again'
        result = _blockquote_content(text)
        assert result == [
            '> \\# Title',
            '> ```',
            '> # not escaped',
            '> ```',
            '> \\# Escaped again',
        ]

    def test_no_escaping_for_non_header_hash(self):
        result = _blockquote_content('value is #FF0000')
        assert result == ['> value is #FF0000']


class TestNormalizeBinaryStatus:
    """Tests for _normalize_binary_status helper."""

    def test_added(self):
        assert _normalize_binary_status('added') == 'Added'

    def test_removed(self):
        assert _normalize_binary_status('removed') == 'Removed'

    def test_modified_binary(self):
        assert _normalize_binary_status('modified_binary') == 'Modified'

    def test_modified_metadata(self):
        assert _normalize_binary_status('modified_metadata') == 'Modified'

    def test_unknown_uses_title(self):
        assert _normalize_binary_status('something') == 'Something'


class TestBuildObjectsByFile:
    """Tests for _build_objects_by_file helper."""

    def _make_data(self, artifact_diff=None, binary_diff=None):
        return ChangeReportData(
            base_revision='abc1234',
            target_revision='def5678',
            generated_at='2026-07-15 12:00 UTC',
            record_name='requirements',
            artifact_diff=artifact_diff,
            binary_diff=binary_diff or [],
        )

    def test_empty(self):
        data = self._make_data()
        result = _build_objects_by_file(data)
        assert result == {}

    def test_artifact_changes(self):
        class FakeBlock:
            class artifact:
                aid = 'X'
                atype = 'REQ'
                fields = {}
                pids = []
            raw_text = ''

        diff = ArtifactDiff(
            added=[('REQ-003', 'REQ', FakeBlock(), 'REQ/REQ-003.md')],
            removed=[('REQ-002', 'REQ', FakeBlock(), 'REQ/REQ-002.md')],
            modified=[
                ArtifactChange(
                    aid='REQ-001',
                    atype='REQ',
                    changed_fields={},
                    content_changed=True,
                    base_raw_text='old',
                    target_raw_text='new',
                    file_path='REQ/REQ-001.md',
                ),
            ],
        )
        data = self._make_data(artifact_diff=diff)
        result = _build_objects_by_file(data)

        assert ('REQ-003', 'REQ', 'Added') in result['REQ/REQ-003.md']
        assert ('REQ-002', 'REQ', 'Removed') in result['REQ/REQ-002.md']
        assert ('REQ-001', 'REQ', 'Modified') in result['REQ/REQ-001.md']


class TestRenderChangedFiles:
    """Tests for _render_changed_files as a table."""

    def _make_data(self, file_diffs, artifact_diff=None, binary_diff=None):
        return ChangeReportData(
            base_revision='abc1234',
            target_revision='def5678',
            generated_at='2026-07-15 12:00 UTC',
            record_name='requirements',
            file_diffs=file_diffs,
            artifact_diff=artifact_diff,
            binary_diff=binary_diff or [],
        )

    def test_empty_file_diffs(self):
        data = self._make_data(file_diffs=[])
        result = _render_changed_files(data)
        assert result == []

    def test_table_header_present(self):
        data = self._make_data(file_diffs=[
            FileDiff(path='REQ/file.md', status=FileStatus.MODIFIED),
        ])
        result = _render_changed_files(data)
        output = '\n'.join(result)
        assert '| Filename | Status | Objects changed |' in output

    def test_file_with_artifacts(self):
        class FakeBlock:
            class artifact:
                aid = 'X'
                atype = 'REQ'
                fields = {}
                pids = []
            raw_text = ''

        diff = ArtifactDiff(
            added=[('REQ-001', 'REQ', FakeBlock(), 'REQ/file.md')],
            removed=[],
            modified=[],
        )
        data = self._make_data(
            file_diffs=[FileDiff(path='REQ/file.md', status=FileStatus.ADDED)],
            artifact_diff=diff,
        )
        result = _render_changed_files(data)
        output = '\n'.join(result)
        assert 'REQ-001 (Added)' in output

    def test_file_without_artifacts(self):
        data = self._make_data(file_diffs=[
            FileDiff(path='REQ/other.md', status=FileStatus.MODIFIED),
        ])
        result = _render_changed_files(data)
        output = '\n'.join(result)
        assert '| REQ/other.md | Modified | — |' in output

    def test_renamed_file(self):
        data = self._make_data(file_diffs=[
            FileDiff(path='REQ/new.md', status=FileStatus.RENAMED, old_path='REQ/old.md'),
        ])
        result = _render_changed_files(data)
        output = '\n'.join(result)
        assert 'Renamed (from REQ/old.md)' in output


class TestFormatTextFragmentEntry:
    """Tests for _format_text_fragment_entry helper."""

    def test_modified(self):
        change = TextFragmentChange(
            status=FileStatus.MODIFIED,
            file_path='docs/file.md',
            old_content='old',
            new_content='new',
            old_lines=(45, 52),
            new_lines=(45, 56),
        )
        result = _format_text_fragment_entry(change)
        assert result == 'Modified (lines 45\u201352 \u2192 lines 45\u201356)'

    def test_added(self):
        change = TextFragmentChange(
            status=FileStatus.ADDED,
            file_path='docs/file.md',
            old_content=None,
            new_content='new content',
            old_lines=None,
            new_lines=(128, 135),
        )
        result = _format_text_fragment_entry(change)
        assert result == 'Added (lines 128\u2013135)'

    def test_removed(self):
        change = TextFragmentChange(
            status=FileStatus.REMOVED,
            file_path='docs/file.md',
            old_content='old content',
            new_content=None,
            old_lines=(210, 218),
            new_lines=None,
        )
        result = _format_text_fragment_entry(change)
        assert result == 'Removed (lines 210\u2013218)'

    def test_added_single_line(self):
        change = TextFragmentChange(
            status=FileStatus.ADDED,
            file_path='docs/file.md',
            old_content=None,
            new_content='one line',
            old_lines=None,
            new_lines=(128, 128),
        )
        result = _format_text_fragment_entry(change)
        assert result == 'Added (lines 128)'

    def test_modified_with_none_ranges(self):
        change = TextFragmentChange(
            status=FileStatus.MODIFIED,
            file_path='docs/file.md',
            old_content='old',
            new_content='new',
            old_lines=None,
            new_lines=None,
        )
        result = _format_text_fragment_entry(change)
        assert result == 'Modified (? \u2192 ?)'


class TestGroupArtifactsByFile:
    """Tests for _group_artifacts_by_file helper."""

    def _make_data(self, artifact_diff):
        return ChangeReportData(
            base_revision='abc1234',
            target_revision='def5678',
            generated_at='2026-07-15 12:00 UTC',
            record_name='requirements',
            artifact_diff=artifact_diff,
        )

    def test_empty_diff(self):
        data = self._make_data(None)
        result = _group_artifacts_by_file(data)
        assert result == {}

    def test_mixed_changes(self):
        # Create a mock ArtifactBlock-like object for added/removed tuples
        class FakeBlock:
            class artifact:
                aid = 'REQ-X'
                atype = 'REQ'
                fields = {}
                pids = []
            raw_text = 'text'

        diff = ArtifactDiff(
            added=[('REQ-003', 'REQ', FakeBlock(), 'REQ/REQ-003.md')],
            removed=[('REQ-002', 'REQ', FakeBlock(), 'REQ/REQ-002.md')],
            modified=[
                ArtifactChange(
                    aid='REQ-001',
                    atype='REQ',
                    changed_fields={'status': ('draft', 'active')},
                    content_changed=True,
                    base_raw_text='old text',
                    target_raw_text='new text',
                    file_path='REQ/REQ-001.md',
                )
            ],
        )
        data = self._make_data(diff)
        result = _group_artifacts_by_file(data)

        assert 'REQ/REQ-003.md' in result
        assert ('REQ-003', 'REQ', 'Added') in result['REQ/REQ-003.md']

        assert 'REQ/REQ-002.md' in result
        assert ('REQ-002', 'REQ', 'Removed') in result['REQ/REQ-002.md']

        assert 'REQ/REQ-001.md' in result
        assert ('REQ-001', 'REQ', 'Modified') in result['REQ/REQ-001.md']

    def test_multiple_artifacts_same_file(self):
        class FakeBlock:
            class artifact:
                aid = 'X'
                atype = 'REQ'
                fields = {}
                pids = []
            raw_text = ''

        diff = ArtifactDiff(
            added=[
                ('REQ-010', 'REQ', FakeBlock(), 'REQ/multi.md'),
                ('REQ-011', 'REQ', FakeBlock(), 'REQ/multi.md'),
            ],
            removed=[],
            modified=[],
        )
        data = self._make_data(diff)
        result = _group_artifacts_by_file(data)
        assert len(result['REQ/multi.md']) == 2


class TestGroupTextFragmentsByFile:
    """Tests for _group_text_fragments_by_file helper."""

    def _make_data(self, text_diff):
        return ChangeReportData(
            base_revision='abc1234',
            target_revision='def5678',
            generated_at='2026-07-15 12:00 UTC',
            record_name='requirements',
            text_diff=text_diff,
        )

    def test_none_text_diff(self):
        data = self._make_data(None)
        result = _group_text_fragments_by_file(data)
        assert result == {}

    def test_fragments_grouped_by_file(self):
        diff = TextBlockDiff(
            added=[TextFragmentChange(
                status=FileStatus.ADDED,
                file_path='REQ/file1.md',
                old_content=None,
                new_content='new text',
                old_lines=None,
                new_lines=(10, 15),
            )],
            removed=[TextFragmentChange(
                status=FileStatus.REMOVED,
                file_path='REQ/file2.md',
                old_content='old text',
                new_content=None,
                old_lines=(20, 25),
                new_lines=None,
            )],
            modified=[TextFragmentChange(
                status=FileStatus.MODIFIED,
                file_path='REQ/file1.md',
                old_content='before',
                new_content='after',
                old_lines=(1, 5),
                new_lines=(1, 8),
            )],
        )
        data = self._make_data(diff)
        result = _group_text_fragments_by_file(data)

        assert 'REQ/file1.md' in result
        assert len(result['REQ/file1.md']) == 2
        assert 'REQ/file2.md' in result
        assert len(result['REQ/file2.md']) == 1


# ---------------------------------------------------------------------------
# Unit tests for render_summary_report
# ---------------------------------------------------------------------------


class TestRenderSummaryReport:
    """Tests for the full render_summary_report function."""

    def _make_report_data(self):
        class FakeBlock:
            class artifact:
                aid = 'REQ-X'
                atype = 'REQ'
                fields = {'contents': 'some text'}
                pids = []
            raw_text = 'some text'

        return ChangeReportData(
            base_revision='v1.0.0',
            target_revision='v1.1.0',
            generated_at='2026-07-15 12:00 UTC',
            record_name='requirements',
            file_diffs=[
                FileDiff(path='REQ/REQ-001.md', status=FileStatus.MODIFIED),
                FileDiff(path='REQ/REQ-003.md', status=FileStatus.ADDED),
                FileDiff(path='REQ/REQ-002.md', status=FileStatus.REMOVED),
                FileDiff(
                    path='REQ/REQ-004.md',
                    status=FileStatus.RENAMED,
                    old_path='REQ/old-name.md',
                ),
            ],
            artifact_diff=ArtifactDiff(
                added=[('REQ-003', 'REQ', FakeBlock(), 'REQ/REQ-003.md')],
                removed=[('REQ-002', 'REQ', FakeBlock(), 'REQ/REQ-002.md')],
                modified=[
                    ArtifactChange(
                        aid='REQ-001',
                        atype='REQ',
                        changed_fields={'status': ('draft', 'active')},
                        content_changed=True,
                        base_raw_text='old text',
                        target_raw_text='new text',
                        file_path='REQ/REQ-001.md',
                    ),
                ],
            ),
            text_diff=TextBlockDiff(
                added=[TextFragmentChange(
                    status=FileStatus.ADDED,
                    file_path='REQ/REQ-001.md',
                    old_content=None,
                    new_content='new para',
                    old_lines=None,
                    new_lines=(50, 55),
                )],
                removed=[],
                modified=[],
            ),
        )

    def test_title_is_summary(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '# Change Report (Summary)' in output

    def test_contains_repo_info(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '## Repository Information' in output
        assert 'v1.0.0' in output
        assert 'v1.1.0' in output

    def test_contains_summary_table(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '## Summary' in output
        assert '| Artifacts added | 1 |' in output
        assert '| Artifacts modified | 1 |' in output
        assert '| Artifacts removed | 1 |' in output

    def test_contains_per_file_headings(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '### REQ/REQ-001.md' in output
        assert '### REQ/REQ-003.md' in output
        assert '### REQ/REQ-002.md' in output

    def test_objects_listed_compactly(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '- REQ REQ-001 (Modified)' in output
        assert '- REQ REQ-003 (Added)' in output
        assert '- REQ REQ-002 (Removed)' in output

    def test_text_fragments_listed(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '**Text fragments**' in output
        assert 'Added (lines 50\u201355)' in output

    def test_no_detailed_changes(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '## Detailed Changes' not in output

    def test_no_content_blocks(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '```text' not in output
        assert '##### Previous' not in output
        assert '##### Current' not in output
        assert 'old text' not in output
        assert 'new text' not in output

    def test_no_attribute_tables(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert '| Attribute | Previous | Current |' not in output
        assert '| status |' not in output

    def test_renamed_file_shows_origin(self):
        data = self._make_report_data()
        output = render_summary_report(data)
        assert 'Renamed (from REQ/old-name.md)' in output

    def test_no_text_fragments_when_text_diff_none(self):
        data = self._make_report_data()
        data.text_diff = None
        output = render_summary_report(data)
        assert '**Text fragments**' not in output

    def test_extraction_error_shown_without_diff(self):
        data = self._make_report_data()
        data.extraction_errors = [
            ExtractionError(
                file_path='REQ/broken.md',
                error_message='YAML parse error at line 5',
                fallback_diff='--- a/REQ/broken.md\n+++ b/REQ/broken.md\n',
            )
        ]
        output = render_summary_report(data)
        assert '### REQ/broken.md' in output
        assert 'Status: Error' in output
        assert 'YAML parse error at line 5' in output
        # No fallback diff in summary mode
        assert '```diff' not in output
        assert '--- a/REQ/broken.md' not in output

    def test_empty_report_no_changes(self):
        data = ChangeReportData(
            base_revision='abc',
            target_revision='def',
            generated_at='2026-07-15 12:00 UTC',
            record_name='requirements',
            file_diffs=[],
            artifact_diff=ArtifactDiff(added=[], removed=[], modified=[]),
            text_diff=None,
        )
        output = render_summary_report(data)
        assert 'No changes detected.' in output


# ---------------------------------------------------------------------------
# Integration tests using CLI
# ---------------------------------------------------------------------------


def _setup_test_repo(tmp_path):
    """Create a test git repo with syntagmax config and sample artifacts."""
    repo = git.Repo.init(tmp_path)

    syntagmax_dir = tmp_path / '.syntagmax'
    syntagmax_dir.mkdir()

    gitignore = tmp_path / '.gitignore'
    gitignore.write_text('.syntagmax/worktrees/\n', encoding='utf-8')

    config = syntagmax_dir / 'config.toml'
    config.write_text("""
base = ".."

[[input]]
name = "requirements"
dir = "REQ"
driver = "obsidian"
atype = "REQ"
marker = "REQ"

[metamodel]
filename = "project.syntagmax"
""", encoding='utf-8')

    metamodel = syntagmax_dir / 'project.syntagmax'
    metamodel.write_text("""
artifact REQ:
    id is string
    attribute contents is mandatory string
    attribute status is mandatory enum [draft, active, retired]
    attribute priority is mandatory enum [low, medium, high, critical]
""", encoding='utf-8')

    req_dir = tmp_path / 'REQ'
    req_dir.mkdir()

    req1 = req_dir / 'REQ-001.md'
    req1.write_text("""[REQ]
The system shall do something.
[id] REQ-001
```yaml
attrs:
  status: draft
  priority: high
```
""", encoding='utf-8')

    req2 = req_dir / 'REQ-002.md'
    req2.write_text("""[REQ]
The system shall do something else.
[id] REQ-002
```yaml
attrs:
  status: draft
  priority: medium
```
""", encoding='utf-8')

    repo.index.add([
        '.gitignore', '.syntagmax/config.toml', '.syntagmax/project.syntagmax',
        'REQ/REQ-001.md', 'REQ/REQ-002.md',
    ])
    repo.index.commit('Initial commit', author=git.Actor('Test', 'test@test.com'))

    # Make changes: modify REQ-001, add REQ-003, remove REQ-002
    req1.write_text("""[REQ]
The system shall do something important.
[id] REQ-001
```yaml
attrs:
  status: active
  priority: critical
```
""", encoding='utf-8')

    req3 = req_dir / 'REQ-003.md'
    req3.write_text("""[REQ]
The system shall have a new feature.
[id] REQ-003
```yaml
attrs:
  status: draft
  priority: low
```
""", encoding='utf-8')

    req2.unlink()

    repo.index.add(['REQ/REQ-001.md', 'REQ/REQ-003.md'])
    repo.index.remove(['REQ/REQ-002.md'])
    repo.index.commit('Update requirements', author=git.Actor('Test', 'test@test.com'))

    return repo, tmp_path


@pytest.fixture
def summary_test_repo(tmp_path):
    return _setup_test_repo(tmp_path)


class TestSummaryIntegration:
    """Integration tests for --summary mode via CLI."""

    def test_summary_console_output(self, summary_test_repo):
        """Test --summary with --output console."""
        _repo, repo_path = summary_test_repo
        runner = CliRunner()
        result = runner.invoke(rms, [
            '--cwd', str(repo_path),
            'change', 'report',
            '--summary',
            '--base', 'HEAD~1',
            '--target', 'HEAD',
            '--output', 'console',
        ])
        assert result.exit_code == 0, f'CLI failed: {result.output}'
        assert '# Change Report (Summary)' in result.output

    def test_summary_no_detailed_changes(self, summary_test_repo):
        """Test that summary mode does NOT include detailed changes."""
        _repo, repo_path = summary_test_repo
        runner = CliRunner()
        result = runner.invoke(rms, [
            '--cwd', str(repo_path),
            'change', 'report',
            '--summary',
            '--base', 'HEAD~1',
            '--target', 'HEAD',
            '--output', 'console',
        ])
        assert result.exit_code == 0
        assert '## Detailed Changes' not in result.output
        assert '```text' not in result.output
        assert '##### Previous' not in result.output
        assert '##### Current' not in result.output

    def test_summary_lists_artifacts(self, summary_test_repo):
        """Test that artifacts are listed by ID and status."""
        _repo, repo_path = summary_test_repo
        runner = CliRunner()
        result = runner.invoke(rms, [
            '--cwd', str(repo_path),
            'change', 'report',
            '--summary',
            '--base', 'HEAD~1',
            '--target', 'HEAD',
            '--output', 'console',
        ])
        assert result.exit_code == 0
        output = result.output
        assert 'REQ-001' in output
        assert 'REQ-003' in output
        assert 'REQ-002' in output
        assert '(Modified)' in output
        assert '(Added)' in output
        assert '(Removed)' in output

    def test_summary_filename_has_suffix(self, summary_test_repo):
        """Test that summary output filename contains -summary."""
        _repo, repo_path = summary_test_repo
        runner = CliRunner()
        result = runner.invoke(rms, [
            '--cwd', str(repo_path),
            'change', 'report',
            '--summary',
            '--base', 'HEAD~1',
            '--target', 'HEAD',
        ])
        assert result.exit_code == 0
        report_dir = repo_path / '.syntagmax' / 'reports' / 'change'
        reports = list(report_dir.glob('*-summary.md'))
        assert len(reports) >= 1, f'Expected summary file, got: {list(report_dir.glob("*.md"))}'

    def test_summary_single_consolidated(self, summary_test_repo):
        """Test --summary combined with --single."""
        _repo, repo_path = summary_test_repo
        runner = CliRunner()
        result = runner.invoke(rms, [
            '--cwd', str(repo_path),
            'change', 'report',
            '--summary',
            '--single',
            '--base', 'HEAD~1',
            '--target', 'HEAD',
        ])
        assert result.exit_code == 0
        report_dir = repo_path / '.syntagmax' / 'reports' / 'change'
        reports = list(report_dir.glob('change-*-summary.md'))
        assert len(reports) == 1, f'Expected consolidated summary, got: {list(report_dir.glob("*.md"))}'

    def test_summary_includes_stats(self, summary_test_repo):
        """Test that summary includes the statistics table."""
        _repo, repo_path = summary_test_repo
        runner = CliRunner()
        result = runner.invoke(rms, [
            '--cwd', str(repo_path),
            'change', 'report',
            '--summary',
            '--base', 'HEAD~1',
            '--target', 'HEAD',
            '--output', 'console',
        ])
        assert result.exit_code == 0
        assert '## Summary' in result.output
        assert '| Artifacts added | 1 |' in result.output
