# SPDX-License-Identifier: MIT
import datetime
from syntagmax.artifact import Artifact, ParentLink, Revision
from syntagmax.config import Config, Params
from syntagmax.render import render_tree_markdown


def test_render_tree_markdown_basic(tmp_path):
    config_file = tmp_path / 'config.toml'
    config_file.write_text('input = []', encoding='utf-8')
    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_file)

    # 1. Setup artifacts
    root = Artifact(config)
    root.aid = 'ROOT'
    root.atype = 'ROOT'
    root.children = {'REQ-001'}

    req1 = Artifact(config)
    req1.aid = 'REQ-001'
    req1.atype = 'REQ'
    req1.pids = ['SYS-001']
    req1.children = {'SUBREQ-001', 'SUBREQ-002'}
    req1.fields = {
        'title': 'Requirement 1',
        'long_desc': 'VeryLongWord' * 10 + ' standard text to check truncation behavior of long fields in the rendering tree output.',
    }

    # Revisions for REQ-001 (sorted by timestamp descending in output)
    rev1 = Revision(
        hash_long='abcdef1234567890abcdef1234567890abcdef12',
        hash_short='abcdef1',
        timestamp=datetime.datetime(2025, 4, 7, 12, 0),
        author_email='alice@example.com',
    )
    rev2 = Revision(
        hash_long='1234567890abcdef1234567890abcdef12345678',
        hash_short='1234567',
        timestamp=datetime.datetime(2025, 4, 8, 15, 30),
        author_email='bob@example.com',
    )
    req1.revisions = {rev1, rev2}

    subreq1 = Artifact(config)
    subreq1.aid = 'SUBREQ-001'
    subreq1.atype = 'SUBREQ'
    subreq1.children = set()
    subreq1.fields = {'status': 'draft'}
    # Test parent links rendering with nominal revision and suspicious flag
    subreq1.parent_links = [ParentLink(pid='REQ-001', nominal_revision='abcdef1', is_suspicious=True)]

    subreq2 = Artifact(config)
    subreq2.aid = 'SUBREQ-002'
    subreq2.atype = 'SUBREQ'
    subreq2.children = set()
    # Test multiple parent links
    subreq2.parent_links = [
        ParentLink(pid='REQ-001', nominal_revision=None, is_suspicious=False),
        ParentLink(pid='OTHER-001', nominal_revision='1234567', is_suspicious=False),
    ]

    artifacts = {'ROOT': root, 'REQ-001': req1, 'SUBREQ-001': subreq1, 'SUBREQ-002': subreq2}

    # 2. Render
    output = render_tree_markdown(artifacts, 'ROOT')
    print('\nRendered Tree:')
    print(output)

    # 3. Assertions
    # ROOT shouldn't show parents/revisions/attributes since it's the top level
    assert ' ROOT: ROOT' in output
    assert 'ROOT: ROOT\n' in output or output.startswith(' ROOT: ROOT')

    # REQ-001 assertions
    assert '  └─REQ: REQ-001' in output
    assert '    │ REQ።REQ-001።None@1234567' in output
    assert '    │ Parents: [SYS-001]' in output
    assert '    │ Revisions:' in output
    # Sorted descending by timestamp: 2025-04-08 should come before 2025-04-07
    lines = output.splitlines()
    rev_lines = [line for line in lines if '- ' in line and ('alice' in line or 'bob' in line)]
    assert len(rev_lines) == 2
    assert '1234567 (2025-04-08 15:30 by bob@example.com)' in rev_lines[0]
    assert 'abcdef1 (2025-04-07 12:00 by alice@example.com)' in rev_lines[1]

    # Truncation check (>60 characters)
    # The long word "VeryLongWord" * 10 is 120 chars long. It should be split/truncated correctly.
    # The code does:
    # if len(field_str) > 60:
    #     field_str = field_str.split()[0]
    #     field_str = field_str[0:60] + '...'
    # For field_str = "VeryLongWord...VeryLongWord standard text..."
    # split()[0] gets "VeryLongWord...VeryLongWord" (120 chars), then truncated to 60 chars.
    assert 'VeryLongWordVeryLongWord' in output
    assert '...' in output

    # SUBREQ-001 assertions
    assert '    ├─SUBREQ: SUBREQ-001' in output
    # Nominal revision and suspicious marker
    assert '    │   Parents: [REQ-001@abcdef1 [!]]' in output

    # SUBREQ-002 assertions
    assert '    └─SUBREQ: SUBREQ-002' in output
    assert '        Parents: [REQ-001, OTHER-001@1234567]' in output
