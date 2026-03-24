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


def perform_impact_analysis(config: Config, artifacts: ArtifactMap, errors: list[str]) -> benedict:

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
                    if (
                        link.nominal_revision != parent.latest_revision.hash_short
                        and link.nominal_revision != parent.latest_revision.hash_long
                    ):
                        link.is_suspicious = True

            if link.is_suspicious:
                actual_rev_obj = parent.latest_revision
                actual_rev_str = 'None'
                if actual_rev_obj:
                    actual_rev_str = f'{actual_rev_obj.hash_short} ({actual_rev_obj.timestamp.strftime("%Y-%m-%d %H:%M")} by {actual_rev_obj.author_email})'

                suspicious_links.append(
                    {
                        'artifact_aid': a.aid,
                        'artifact_atype': a.atype,
                        'parent_aid': parent.aid,
                        'parent_atype': parent.atype,
                        'nominal_revision': link.nominal_revision,
                        'actual_revision': actual_rev_str,
                    }
                )

    impact_data['suspicious_links'] = suspicious_links
    impact_data['total_suspicious'] = len(suspicious_links)

    if suspicious_links:
        suspicious_aids = {link['artifact_aid'] for link in suspicious_links}
        updated_aids = {link['parent_aid'] for link in suspicious_links}
        impact_data['suspicious_tree'] = _generate_suspicious_tree(artifacts, suspicious_aids, updated_aids)

    _render_impact_report(impact_data, config)


CONST_I_CHAR = '│'
CONST_T_CHAR = '├─'
CONST_L_CHAR = '└─'


def _generate_suspicious_tree(artifacts: ArtifactMap, suspicious_aids: set[str], updated_aids: set[str]) -> str:
    cache: dict[str, bool] = {}

    def has_suspicious_descendant(aid: str) -> bool:
        if aid in cache:
            return cache[aid]
        res = False
        if aid in suspicious_aids:
            res = True
        elif aid in artifacts:
            for cid in artifacts[aid].children:
                if has_suspicious_descendant(cid):
                    res = True
                    break
        cache[aid] = res
        return res

    def render_node(aid: str, indent: str = '', last: bool = True, top: bool = True) -> str:
        if not has_suspicious_descendant(aid):
            return ''

        if aid not in artifacts:
            return ''

        a = artifacts[aid]
        this_indent = indent + (CONST_L_CHAR if last else CONST_T_CHAR) if not top else ''

        status = ''
        if aid in suspicious_aids:
            status += ' [!] OUTDATED'
        if aid in updated_aids:
            status += ' [*] UPDATED'

        label = f'{a.atype}:{a.aid}' if a.atype != 'ROOT' else a.aid
        line = f'{this_indent}{label}{status}\n'

        new_indent = indent + ((CONST_I_CHAR + ' ') if not last else '  ') if not top else ''

        relevant_children = [cid for cid in sorted(a.children) if has_suspicious_descendant(cid)]

        res = line
        for i, cid in enumerate(relevant_children):
            res += render_node(cid, new_indent, i == len(relevant_children) - 1, False)

        return res

    return render_node('ROOT').strip()


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


def _render_impact_report(impact_data: benedict, config: Config):
    if not impact_data:
        return

    if config.impact.output_format == 'rich':
        _print_impact_console(impact_data)
    elif config.impact.output_format == 'markdown':
        _publish_impact_report(impact_data, config)


def _print_impact_console(impact_data: benedict):
    from rich.table import Table

    if impact_data['total_suspicious'] == 0:
        rich.print('[green]No suspicious links found.[/green]')
        return

    table = Table(title='Impact Analysis: Suspicious Links')
    table.add_column('Artifact', style='cyan')
    table.add_column('Parent', style='magenta')
    table.add_column('Nominal Rev', style='yellow')
    table.add_column('Actual Rev', style='green')

    for link in impact_data['suspicious_links']:
        table.add_row(
            f'{link["artifact_atype"]}:{link["artifact_aid"]}',
            f'{link["parent_atype"]}:{link["parent_aid"]}',
            str(link['nominal_revision']),
            str(link['actual_revision']),
        )

    rich.print(table)

    if 'suspicious_tree' in impact_data:
        from rich.panel import Panel

        rich.print(Panel(impact_data['suspicious_tree'], title='Suspicious Tree', expand=False))


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
