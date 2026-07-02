# SPDX-License-Identifier: MIT

from benedict import benedict
from syntagmax.report import Report


def test_report_render_all_sections():
    report = Report(
        errors=['Error 1', 'Error 2'],
        tree_text='ROOT\n\u251c\u2500REQ: REQ-001\n\u2514\u2500REQ: REQ-002',
        metrics=benedict(
            {
                'total_requirements': 5,
                'requirements_by_status': [
                    {'status': 'active', 'count': 3},
                    {'status': 'draft', 'count': 2},
                ],
                'requirements_without_verify_pct': 20.0,
                'requirements_with_tbd_pct': 10.0,
            }
        ),
        impact=benedict(
            {
                'total_suspicious': 1,
                'suspicious_links': [
                    {
                        'artifact_aid': 'REQ-002',
                        'artifact_atype': 'REQ',
                        'parent_aid': 'SYS-001',
                        'parent_atype': 'SYS',
                        'nominal_revision': 'abc1234',
                        'actual_revision': 'def5678',
                    }
                ],
                'suspicious_tree': 'ROOT\n\u2514\u2500SYS:SYS-001 [*] UPDATED\n  \u2514\u2500REQ:REQ-002 [!] OUTDATED',
            }
        ),
        ai_results=[
            {
                'aid': 'REQ-001',
                'atype': 'REQ',
                'ambiguity': 0.2,
                'completeness': 0.8,
                'verifiability': 0.9,
                'singularity': 0.7,
            }
        ],
    )

    md = report.render()
    assert '## Errors' in md
    assert 'Error 1' in md
    assert '## Artifact Tree' in md
    assert 'REQ-001' in md
    assert '## Metrics' in md
    assert '## Impact Analysis' in md
    assert '## AI Analysis' in md
    assert '| REQ:REQ-001 |' in md


def test_report_render_empty():
    report = Report()
    md = report.render()
    assert '# Analysis Report' in md
    assert '## Errors' not in md
    assert '## Metrics' not in md
