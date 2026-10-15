# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: Tests for the syntagmax.api facade trace/publish methods (R1, R2).

from pathlib import Path

from syntagmax import api

# The obsidian-driver example carries SYS/REQ/SRC/TEST atypes with REQ->SYS
# parent links, so it exercises forward/reverse/flat traces and a full publish.
EXAMPLE_CONFIG = Path(__file__).parents[1] / 'example' / 'obsidian-driver' / '.syntagmax' / 'config.toml'


def _session() -> api.Session:
    return api.open_project(EXAMPLE_CONFIG, options=api.Options(no_git=True))


# --- Session.trace (R1) ----------------------------------------------------


def test_trace_forward_header_and_rows():
    result = _session().trace('REQ', 'SYS')
    assert result.direction == 'forward'
    assert result.child_type == 'REQ'
    assert result.parent_type == 'SYS'
    # Forward: lead = child (REQ), linked = parent (SYS).
    assert result.header[:3] == ['RecordNumber', 'ChildID', 'ParentID']
    assert result.rows, 'forward REQ->SYS should yield rows'
    lead_ids = {row[1] for row in result.rows}
    assert any(lead.startswith('REQ-') for lead in lead_ids)
    # At least one REQ links to a SYS parent.
    assert any(row[2].startswith('SYS-') for row in result.rows)


def test_trace_reverse_header():
    result = _session().trace('REQ', 'SYS', direction='reverse')
    assert result.direction == 'reverse'
    # Reverse: lead = parent (SYS), linked = child (REQ).
    assert result.header[:3] == ['RecordNumber', 'ParentID', 'ChildID']
    assert result.rows
    assert any(row[1].startswith('SYS-') for row in result.rows)


def test_trace_flat_combines_links():
    flat = _session().trace('REQ', 'SYS', flat=True)
    # In flat mode each lead appears exactly once.
    lead_ids = [row[1] for row in flat.rows]
    assert len(lead_ids) == len(set(lead_ids))


def test_trace_record_names_populated():
    result = _session().trace('REQ', 'SYS')
    assert result.record_names
    # Every referenced id maps to its (non-None) input record name.
    for name in result.record_names.values():
        assert isinstance(name, str)


def test_render_trace_csv_and_tsv_round_trip():
    result = _session().trace('REQ', 'SYS')
    csv_text = api.render_trace(result, delimiter=',')
    tsv_text = api.render_trace(result, delimiter='\t')
    header = csv_text.split('\n', 1)[0]
    assert header.split(',') == result.header
    assert '\t' in tsv_text.split('\n', 1)[0]
    # Row count (excluding header + trailing newline) matches the result rows.
    csv_body = [line for line in csv_text.split('\n')[1:] if line]
    assert len(csv_body) == len(result.rows)


def test_trace_unresolved_link_visible():
    # A trace to a non-existent parent type still emits every lead (left outer
    # join), with an empty linked id rather than raising.
    result = _session().trace('REQ', 'NOSUCH')
    assert result.rows
    assert all(row[2] == '' for row in result.rows)


# --- Session.publish (R2) --------------------------------------------------


def test_publish_returns_markdown_and_counts():
    result = _session().publish()
    assert isinstance(result.markdown, str)
    assert result.markdown.strip()
    assert result.artifact_count > 0
    assert result.text_block_count >= 0
    # Consolidated publication contains real artifact ids.
    assert 'REQ-001' in result.markdown or 'SYS-001' in result.markdown


def test_publish_single_is_default():
    default = _session().publish()
    explicit = _session().publish(single=True)
    assert default.artifact_count == explicit.artifact_count
