# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-06-20
# Description: Unified report for all analysis outputs.

from dataclasses import dataclass, field
from pathlib import Path

from benedict import benedict
from jinja2 import Environment, FileSystemLoader, select_autoescape


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    tree_text: str | None = None
    metrics: benedict | None = None
    impact: benedict | None = None
    ai_results: list[dict] | None = None

    def render(self) -> str:
        from syntagmax.i18n import get_translations

        resources_dir = Path(__file__).parent / 'resources'
        env = Environment(
            loader=FileSystemLoader(str(resources_dir)),
            autoescape=select_autoescape(default=False),
            extensions=['jinja2.ext.i18n'],
        )
        env.install_gettext_translations(get_translations())
        template = env.get_template('report.j2')
        return template.render(report=self)
