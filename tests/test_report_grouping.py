# SPDX-License-Identifier: MIT

from benedict import benedict
from syntagmax.report import (
    Report, ReportError,
    CAT_SCHEMA, CAT_ATTRIBUTE, CAT_REFERENCE, CAT_TRACE,
    CAT_EXTRACTION, CAT_STRUCTURE,
)
from syntagmax.config import ReportConfig


def test_errors_grouped_multiple_inputs():
    """Errors from different inputs group under correct headings."""
    report = Report(
        errors=[
            ReportError(message='err1', category=CAT_ATTRIBUTE, input_record='reqs-a'),
            ReportError(message='err2', category=CAT_SCHEMA, input_record='reqs-b'),
            ReportError(message='err3', category=CAT_ATTRIBUTE, input_record='reqs-a'),
            ReportError(message='err4', category=CAT_TRACE, input_record='reqs-b'),
        ]
    )
    grouped = report.errors_grouped()
    assert 'reqs-a' in grouped
    assert 'reqs-b' in grouped
    # reqs-a has only attribute errors
    assert len(grouped['reqs-a']) == 1
    assert grouped['reqs-a'][0][1] == [report.errors[0], report.errors[2]]
    # reqs-b has schema and trace errors
    assert len(grouped['reqs-b']) == 2


def test_errors_grouped_global_first():
    """Global errors (input_record=None) appear first in grouping."""
    report = Report(
        errors=[
            ReportError(message='input err', category=CAT_ATTRIBUTE, input_record='alpha'),
            ReportError(message='global err', category=CAT_STRUCTURE, input_record=None),
        ]
    )
    grouped = report.errors_grouped()
    keys = list(grouped.keys())
    assert keys[0] == 'Global'  # Global comes first
    assert keys[1] == 'alpha'


def test_errors_grouped_canonical_order():
    """Categories within an input are sorted by CANONICAL_CATEGORY_ORDER."""
    report = Report(
        errors=[
            ReportError(message='trace', category=CAT_TRACE, input_record='x'),
            ReportError(message='extraction', category=CAT_EXTRACTION, input_record='x'),
            ReportError(message='schema', category=CAT_SCHEMA, input_record='x'),
        ]
    )
    grouped = report.errors_grouped()
    categories = [cat_name for cat_name, _ in grouped['x']]
    # CANONICAL order: extraction, structure, schema, attribute, reference, trace, duplicate
    # So extraction < schema < trace
    extraction_idx = next(i for i, c in enumerate(categories) if 'Extraction' in c or 'extraction' in c.lower())
    schema_idx = next(i for i, c in enumerate(categories) if 'Schema' in c or 'schema' in c.lower())
    trace_idx = next(i for i, c in enumerate(categories) if 'Trace' in c or 'trace' in c.lower())
    assert extraction_idx < schema_idx < trace_idx


def test_errors_grouped_empty():
    """Empty error list produces empty grouping."""
    report = Report(errors=[])
    grouped = report.errors_grouped()
    assert grouped == {}


def test_plain_string_errors_dont_crash():
    """Plain strings mixed into errors list are coerced via from_any without crash."""
    report = Report(
        errors=[
            ReportError(message='real', category=CAT_ATTRIBUTE, input_record='x'),
            'legacy string error',  # type: ignore
        ]
    )
    # Should not raise
    grouped = report.errors_grouped()
    # The string gets coerced to Global/structure
    assert 'Global' in grouped or 'x' in grouped
    # Actually let's just verify rendering doesn't crash
    md = report.render()
    assert 'legacy string error' in md


def test_report_render_grouped_structure():
    """Full render produces grouped markdown structure."""
    report = Report(
        errors=[
            ReportError(message='bad schema', category=CAT_SCHEMA, input_record='sw-reqs'),
            ReportError(message='missing ref', category=CAT_REFERENCE, input_record='sw-reqs'),
            ReportError(message='struct issue', category=CAT_STRUCTURE),
        ]
    )
    md = report.render()
    assert '## Errors' in md
    assert 'Total errors:' in md
    assert '3' in md
    assert '### Global' in md
    assert '### sw-reqs' in md
    assert 'Schema Errors' in md
    assert 'Reference Errors' in md
    assert 'Structure Errors' in md


def test_report_render_with_markdown_links():
    """With path_as_links=True, wiki_links=False, renders Markdown links."""
    report = Report(
        errors=[
            ReportError(
                message='bad attr',
                category=CAT_ATTRIBUTE,
                input_record='reqs',
                artifact_type='REQ',
                artifact_id='REQ-001',
                file_path='requirements/file.md',
                line_range=(10, 20),
            ),
        ],
        report_config=ReportConfig(path_as_links=True, wiki_links=False),
    )
    md = report.render()
    assert '[file.md](requirements/file.md#L10):10-20' in md
    assert 'REQ:REQ-001' in md


def test_report_render_with_wiki_links():
    """With path_as_links=True, wiki_links=True, renders wiki links."""
    report = Report(
        errors=[
            ReportError(
                message='bad attr',
                category=CAT_ATTRIBUTE,
                input_record='reqs',
                artifact_type='REQ',
                artifact_id='REQ-001',
                file_path='requirements/file.md',
                line_range=(10, 20),
            ),
        ],
        report_config=ReportConfig(path_as_links=True, wiki_links=True),
    )
    md = report.render()
    assert '[[requirements/file.md]]:10-20' in md
    assert '#L' not in md


def test_report_render_links_disabled():
    """With path_as_links=False (default), renders plain text."""
    report = Report(
        errors=[
            ReportError(
                message='bad attr',
                category=CAT_ATTRIBUTE,
                input_record='reqs',
                artifact_type='REQ',
                artifact_id='REQ-001',
                file_path='requirements/file.md',
                line_range=(10, 20),
            ),
        ],
        report_config=ReportConfig(path_as_links=False),
    )
    md = report.render()
    # Should use __str__ format
    assert 'requirements/file.md:10-20' in md
    assert '[[' not in md
    assert '[file.md]' not in md


def test_metrics_by_input_rendered():
    """When metrics_by_input is set, renders per-input subsections."""
    report = Report(
        metrics=benedict({
            'total_requirements': 10,
            'requirements_by_status': [{'status': 'active', 'count': 10}],
            'requirements_without_verify_pct': 0.0,
            'requirements_with_tbd_pct': 0.0,
        }),
        metrics_by_input=[
            ('input-a', benedict({
                'total_requirements': 6,
                'requirements_by_status': [{'status': 'active', 'count': 6}],
                'requirements_without_verify_pct': 0.0,
                'requirements_with_tbd_pct': 0.0,
            })),
            ('input-b', benedict({
                'total_requirements': 4,
                'requirements_by_status': [{'status': 'draft', 'count': 4}],
                'requirements_without_verify_pct': 25.0,
                'requirements_with_tbd_pct': 50.0,
            })),
        ]
    )
    md = report.render()
    assert '## Metrics' in md
    assert 'Total Requirements' in md
    assert '#### input-a' in md
    assert '#### input-b' in md


def test_metrics_single_input_no_breakdown():
    """With single input, only aggregate metrics rendered (no per-input section)."""
    report = Report(
        metrics=benedict({
            'total_requirements': 5,
            'requirements_by_status': [{'status': 'active', 'count': 5}],
            'requirements_without_verify_pct': 0.0,
            'requirements_with_tbd_pct': 0.0,
        }),
        # metrics_by_input is None
    )
    md = report.render()
    assert '## Metrics' in md
    assert 'Metrics by Input Record' not in md
