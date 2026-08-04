# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-06-20
# Description: Unified report for all analysis outputs.

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from benedict import benedict
from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from syntagmax.config import ReportConfig


CAT_SCHEMA = 'schema'
CAT_ATTRIBUTE = 'attribute'
CAT_REFERENCE = 'reference'
CAT_TRACE = 'trace'
CAT_DUPLICATE = 'duplicate'
CAT_EXTRACTION = 'extraction'
CAT_STRUCTURE = 'structure'

GLOBAL_INPUT = '__global__'

CANONICAL_CATEGORY_ORDER = [
    CAT_EXTRACTION,
    CAT_STRUCTURE,
    CAT_SCHEMA,
    CAT_ATTRIBUTE,
    CAT_REFERENCE,
    CAT_TRACE,
    CAT_DUPLICATE,
]


@dataclass
class ReportError:
    message: str
    category: str
    input_record: str | None = None
    artifact_id: str | None = None
    artifact_type: str | None = None
    file_path: str | None = None
    line_range: tuple[int, int] | None = None

    @classmethod
    def from_any(cls, err: 'ReportError | str') -> 'ReportError':
        if isinstance(err, ReportError):
            return err
        return cls(message=str(err), category=CAT_STRUCTURE)

    def __str__(self) -> str:
        loc = ''
        if self.artifact_type and self.artifact_id and self.file_path:
            lines = f':{self.line_range[0]}-{self.line_range[1]}' if self.line_range else ''
            loc = f' ({self.artifact_type}\u1362{self.artifact_id}\u1362{self.file_path}{lines})'
        elif self.artifact_type and self.artifact_id:
            loc = f' ({self.artifact_type}\u1362{self.artifact_id})'
        elif self.file_path:
            loc = f' ({self.file_path})'
        return f'{self.message}{loc}'


def format_error(error: ReportError, report_config: 'ReportConfig | None' = None) -> str:
    """Format a ReportError for Markdown output, optionally rendering file links."""
    if not report_config or not report_config.path_as_links or not error.file_path:
        return str(error)

    # Build link
    from pathlib import PurePosixPath

    path = error.file_path
    filename = PurePosixPath(path).name

    if report_config.wiki_links:
        # Wiki-link style: [[path/to/file.md]] — no line anchors
        link = f'[[{path}]]'
    else:
        # Standard Markdown link with line anchor
        anchor = f'#L{error.line_range[0]}' if error.line_range else ''
        link = f'[{filename}]({path}{anchor})'

    # Build the formatted string
    parts = [error.message]
    loc_parts = []
    if error.artifact_type and error.artifact_id:
        loc_parts.append(f'{error.artifact_type}:{error.artifact_id}')
    loc_parts.append(link)

    if loc_parts:
        parts.append(f' ({" in ".join(loc_parts)})')

    return ''.join(parts)


@dataclass
class Report:
    errors: list[ReportError] = field(default_factory=list)
    tree_text: str | None = None
    metrics: benedict | None = None
    metrics_by_input: list[tuple[str, benedict]] | None = None
    impact: benedict | None = None
    tasks_summary: dict | None = None
    report_config: 'ReportConfig | None' = None

    def errors_grouped(self) -> dict[str, list[tuple[str, list['ReportError']]]]:
        """Group errors by input record, then by category.

        Returns OrderedDict: {input_name: [(category_display, [errors])]}
        'Global' comes first if present, then input records alphabetically.
        Categories within each input are sorted by CANONICAL_CATEGORY_ORDER.
        """
        from collections import OrderedDict

        from syntagmax.i18n import _

        CATEGORY_DISPLAY = {
            CAT_EXTRACTION: _('Extraction Errors'),
            CAT_STRUCTURE: _('Structure Errors'),
            CAT_SCHEMA: _('Schema Errors'),
            CAT_ATTRIBUTE: _('Attribute Errors'),
            CAT_REFERENCE: _('Reference Errors'),
            CAT_TRACE: _('Trace Errors'),
            CAT_DUPLICATE: _('Duplicate Errors'),
        }

        # Normalize all errors
        normalized = [ReportError.from_any(e) for e in self.errors]

        # Group by input_record
        by_input: dict[str, list[ReportError]] = {}
        for err in normalized:
            key = err.input_record or GLOBAL_INPUT
            by_input.setdefault(key, []).append(err)

        # Build result with canonical category ordering
        result: OrderedDict[str, list[tuple[str, list[ReportError]]]] = OrderedDict()

        # Global first
        if GLOBAL_INPUT in by_input:
            global_label = _('Global')
            result[global_label] = self._group_by_category(by_input[GLOBAL_INPUT], CATEGORY_DISPLAY)

        # Then input records alphabetically
        for input_name in sorted(k for k in by_input if k != GLOBAL_INPUT):
            result[input_name] = self._group_by_category(by_input[input_name], CATEGORY_DISPLAY)

        return result

    def _group_by_category(
        self, errors: list['ReportError'], display_map: dict[str, str]
    ) -> list[tuple[str, list['ReportError']]]:
        """Group a list of errors by category in canonical order."""
        by_cat: dict[str, list[ReportError]] = {}
        for err in errors:
            by_cat.setdefault(err.category, []).append(err)

        result = []
        for cat in CANONICAL_CATEGORY_ORDER:
            if cat in by_cat:
                display_name = display_map.get(cat, cat)
                result.append((display_name, by_cat[cat]))

        # Any unknown categories at the end
        for cat in by_cat:
            if cat not in CANONICAL_CATEGORY_ORDER:
                display_name = display_map.get(cat, cat)
                result.append((display_name, by_cat[cat]))

        return result

    def render(self) -> str:
        from syntagmax.i18n import get_translations

        resources_dir = Path(__file__).parent / 'resources'
        env = Environment(
            loader=FileSystemLoader(str(resources_dir)),
            autoescape=select_autoescape(default=False),
            extensions=['jinja2.ext.i18n'],
        )
        env.install_gettext_translations(get_translations())
        env.filters['format_error'] = lambda e: format_error(e, self.report_config)
        template = env.get_template('report.j2')
        return template.render(report=self)
