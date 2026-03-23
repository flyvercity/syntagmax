# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-22
# Description: Syntagmax init command.

from pathlib import Path
from typing import Any

from syntagmax.config import ConfigFile, MetricsConfig, ImpactConfig, AIConfig


def get_desc(field: Any) -> str:
    return field.description or field.title or field.alias or 'No description'


def generate_toml() -> str:
    toml_str: list[str] = []

    # Global ConfigFile
    for name, field in ConfigFile.model_fields.items():
        if name in ['input', 'metrics', 'impact', 'ai', 'metamodel']:
            continue
        desc = get_desc(field)
        default = field.default
        toml_str.append(f'# {desc}')
        if name == 'base':
            toml_str.append(f'{name} = ".."')
        else:
            toml_str.append(f'# {name} = "{default}"')
    toml_str.append('')

    # Input
    toml_str.append('[[input]]')
    toml_str.append('name = "requirements"')
    toml_str.append('dir = "REQ"')
    toml_str.append('driver = "obsidian"')
    toml_str.append('')

    # Metamodel
    toml_str.append('[metamodel]')
    toml_str.append('filename = "project.syntagmax"')
    toml_str.append('')

    # Metrics
    toml_str.append('# [metrics]')
    for name, field in MetricsConfig.model_fields.items():
        desc = get_desc(field)
        default = field.default
        if isinstance(default, str):
            val = f'"{default}"'
        elif isinstance(default, bool):
            val = str(default).lower()
        elif default is None:
            val = '""'
        else:
            val = str(default)
        toml_str.append(f'# {desc}')
        toml_str.append(f'# {name} = {val}')
    toml_str.append('')

    # Impact
    toml_str.append('# [impact]')
    for name, field in ImpactConfig.model_fields.items():
        desc = get_desc(field)
        default = field.default
        if isinstance(default, str):
            val = f'"{default}"'
        elif isinstance(default, bool):
            val = str(default).lower()
        elif default is None:
            val = '""'
        else:
            val = str(default)
        toml_str.append(f'# {desc}')
        toml_str.append(f'# {name} = {val}')
    toml_str.append('')

    # AI
    toml_str.append('# [ai]')
    for name, field in AIConfig.model_fields.items():
        desc = get_desc(field)
        default = field.default
        if isinstance(default, str):
            val = f'"{default}"'
        elif isinstance(default, bool):
            val = str(default).lower()
        elif default is None:
            val = '""'
        else:
            val = str(default)
        toml_str.append(f'# {desc}')
        toml_str.append(f'# {name} = {val}')
    toml_str.append('')

    return '\n'.join(toml_str)


METAMODEL_CONTENT = """artifact SYS:
    attribute id is mandatory string
    attribute contents is mandatory string
"""


def init_project(cwd: str | None = None) -> None:
    base_dir = Path(cwd) if cwd else Path.cwd()
    syntagmax_dir = base_dir / '.syntagmax'

    if not syntagmax_dir.exists():
        syntagmax_dir.mkdir(parents=True)

    config_file = syntagmax_dir / 'config.toml'
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(generate_toml())

    metamodel_file = syntagmax_dir / 'project.syntagmax'
    with open(metamodel_file, 'w', encoding='utf-8') as f:
        f.write(METAMODEL_CONTENT)
