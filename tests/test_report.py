# SPDX-License-Identifier: MIT

from benedict import benedict
from syntagmax.report import (
    CAT_ATTRIBUTE,
    CAT_STRUCTURE,
    Report,
    ReportError,
)


def test_report_render_all_sections():
    report = Report(
        errors=[
            ReportError(message='Error 1', category=CAT_STRUCTURE),
            ReportError(message='Error 2', category=CAT_ATTRIBUTE, input_record='test-input'),
        ],
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
    )

    md = report.render()
    assert '## Errors' in md
    assert '### Global' in md
    assert '#### Structure Errors (1)' in md
    assert 'Error 1' in md
    assert '### test-input' in md
    assert '#### Attribute Errors (1)' in md
    assert 'Error 2' in md
    assert '## Artifact Tree' in md
    assert 'REQ-001' in md
    assert '## Metrics' in md
    assert '## Impact Analysis' in md


def test_report_render_empty():
    report = Report()
    md = report.render()
    assert '# Analysis Report' in md
    assert '## Errors' not in md
    assert '## Metrics' not in md


def test_report_render_undefined_id():
    report = Report(
        impact=benedict(
            {
                'total_suspicious': 1,
                'suspicious_links': [
                    {
                        'artifact_aid': '<undefined>',
                        'artifact_atype': 'REQ',
                        'parent_aid': '<undefined>',
                        'parent_atype': 'SYS',
                        'nominal_revision': 'abc1234',
                        'actual_revision': 'def5678',
                    }
                ],
            }
        ),
    )
    md = report.render()
    assert '| REQ:`<undefined>` | SYS:`<undefined>` |' in md
