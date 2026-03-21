# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-21
# Description: Impact analysis for a tree of artifacts.

import logging as lg
from pathlib import Path

import rich
from babel import Locale
from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po
from babel.numbers import format_number, format_percent
from benedict import benedict
from jinja2 import Environment, FileSystemLoader, select_autoescape

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config
from syntagmax.git_utils import is_dirty


def perform_impact_analysis(config: Config, artifacts: ArtifactMap, errors: list[str]) -> benedict:
    if not config.impact.enabled:
        return benedict()

    # Check for dirty worktree
    if is_dirty(config) and not config.params.get('allow_dirty_worktree', False):
        errors.append("Repository is dirty. Commit your changes or use --allow-dirty-worktree.")
        return benedict()

    impact_data = benedict()
    suspicious_links = []

    for a in artifacts.values():
        if a.atype == 'ROOT':
            continue

        for link in a.parent_links:
            parent = artifacts.get(link.pid)
            if not parent:
                continue

            # Impact analysis logic
            if link.nominal_revision == 'older':
                # via timestamp
                if a.latest_revision and parent.latest_revision:
                    if parent.latest_revision.timestamp > a.latest_revision.timestamp:
                        link.is_suspicious = True
            elif link.nominal_revision:
                # via commit
                if parent.latest_revision:
                    # Compare nominal revision with parent's latest revision
                    # We compare short hash for simplicity as it is what user likely provides
                    if link.nominal_revision != parent.latest_revision.hash_short and \
                       link.nominal_revision != parent.latest_revision.hash_long:
                        link.is_suspicious = True

            if link.is_suspicious:
                suspicious_links.append({
                    'artifact_aid': a.aid,
                    'artifact_atype': a.atype,
                    'parent_aid': parent.aid,
                    'parent_atype': parent.atype,
                    'nominal_revision': link.nominal_revision,
                    'actual_revision': parent.latest_revision.hash_short if parent.latest_revision else 'None'
                })

    impact_data['suspicious_links'] = suspicious_links
    impact_data['total_suspicious'] = len(suspicious_links)

    return impact_data


def _load_catalog(locale_dir: Path, locale: str) -> Catalog | None:
    po_path = locale_dir / locale / 'LC_MESSAGES' / 'messages.po'
    if not po_path.exists():
        return None
    with open(po_path, 'rb') as f:
        return read_po(f, locale=locale)


def _make_gettext(catalog: Catalog | None):
    def gettext_as_is(msgid: str) -> str:
        return msgid

    if catalog is None:
        return gettext_as_is

    def gettext(msgid: str) -> str:
        msg = catalog.get(msgid)
        if msg is not None and msg.string:
            return str(msg.string)
        return msgid

    return gettext


def render_impact_report(impact_data: benedict, config: Config):
    if not config.impact.enabled or not impact_data:
        return

    if config.impact.output_format == 'rich':
        _print_impact_console(impact_data)
    elif config.impact.output_format == 'markdown':
        _publish_impact_report(impact_data, config)


def _print_impact_console(impact_data: benedict):
    from rich.table import Table
    if impact_data['total_suspicious'] == 0:
        rich.print("[green]No suspicious links found.[/green]")
        return

    table = Table(title='Impact Analysis: Suspicious Links')
    table.add_column('Artifact', style='cyan')
    table.add_column('Parent', style='magenta')
    table.add_column('Nominal Rev', style='yellow')
    table.add_column('Actual Rev', style='green')

    for link in impact_data['suspicious_links']:
        table.add_row(
            f"{link['artifact_atype']}:{link['artifact_aid']}",
            f"{link['parent_atype']}:{link['parent_aid']}",
            str(link['nominal_revision']),
            str(link['actual_revision'])
        )

    rich.print(table)


def _publish_impact_report(impact_data: benedict, config: Config):
    output = config.impact.output_file
    resources_dir = Path(__file__).parent / 'resources'
    template_path = config.impact.template

    if template_path:
        loader_dir = Path(template_path).parent
        template_name = Path(template_path).name
    else:
        loader_dir = resources_dir
        template_name = 'impact.j2'

    locale_dir = resources_dir / 'locales'
    locale = config.impact.locale or 'en'
    catalog = _load_catalog(locale_dir, locale)
    gettext_fn = _make_gettext(catalog)
    
    env = Environment(
        loader=FileSystemLoader(str(loader_dir)),
        extensions=['jinja2.ext.i18n'],
        autoescape=select_autoescape(default=False),
    )
    env.install_gettext_callables(  # type: ignore[attr-defined]
        gettext=gettext_fn,
        ngettext=lambda s, p, n: p if n != 1 else s,  # type: ignore
    )

    try:
        loc = Locale.parse(locale)
    except Exception:
        loc = None

    if loc:
        env.filters['format_number'] = lambda x: format_number(float(x), locale=loc)  # type: ignore
        env.filters['format_percent'] = lambda x: format_percent(float(x) / 100.0, locale=loc)  # type: ignore
    else:
        env.filters['format_number'] = lambda x: str(x)
        env.filters['format_percent'] = lambda x: f'{round(float(x), 1)}%'  # type: ignore

    template = env.get_template(template_name)
    markdown = template.render(impact=impact_data)

    if output == 'console':
        rich.print(markdown)
    else:
        output_file = Path(output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        lg.info(f'Writing impact report to {output_file}')
        output_file.write_text(markdown, encoding='utf-8')
