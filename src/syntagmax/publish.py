# Author: Boris Resnick
# Created: 2026-02-15
# Description: Publishes the project metrics to a file using Jinja templates and localization.

import logging as lg
from pathlib import Path

import rich
from babel import Locale
from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po
from babel.numbers import format_number, format_percent
from benedict import benedict
from jinja2 import Environment, FileSystemLoader, select_autoescape

from syntagmax.config import Config


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


def publish_metrics(metrics: benedict, config: Config):
    output = config.metrics.output_file
    resources_dir = Path(__file__).parent / 'resources'
    template_path = config.metrics.template

    if template_path:
        loader_dir = Path(template_path).parent.resolve()
        template_name = Path(template_path).name
    else:
        loader_dir = resources_dir
        template_name = 'metrics.j2'

    locale_dir = resources_dir / 'locales'
    locale = config.metrics.locale or 'en'
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
    markdown = template.render(metrics=metrics)

    if output == 'console':
        rich.print(markdown)
    else:
        output_file = Path(output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        lg.info(f'Writing metrics to {output_file}')
        output_file.write_text(markdown, encoding='utf-8')
