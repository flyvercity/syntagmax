# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-09
# Description: Reads Obsidian vault settings (app.json) for attachment path resolution.

import json
import logging as lg
from pathlib import Path


def read_obsidian_attachment_path(base_dir: Path, root_override: str | None = None) -> str | None:
    """Read the attachmentFolderPath from Obsidian's app.json.

    Args:
        base_dir: The project base directory.
        root_override: Optional override path to the .obsidian directory (relative to base_dir).

    Returns:
        The raw attachmentFolderPath string from app.json, or None if unavailable.
        The returned path is NOT yet resolved to an absolute path — callers must
        handle note-relative paths (starting with './') separately.
    """
    if root_override:
        obsidian_dir = (base_dir / root_override).resolve()
    else:
        obsidian_dir = (base_dir / '.obsidian').resolve()

    app_json_path = obsidian_dir / 'app.json'

    try:
        content = app_json_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        lg.warning(f'Obsidian integration enabled but app.json not found: {app_json_path}')
        return None
    except PermissionError:
        lg.warning(f'Obsidian integration enabled but app.json is not readable: {app_json_path}')
        return None

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        lg.warning(f'Obsidian integration enabled but app.json contains malformed JSON: {e}')
        return None

    attachment_path = data.get('attachmentFolderPath')
    if not attachment_path:
        lg.warning('Obsidian integration enabled but attachmentFolderPath not set in app.json')
        return None

    return attachment_path



def read_obsidian_strict_line_breaks(base_dir: Path, root_override: str | None = None) -> bool | None:
    """Read the strictLineBreaks setting from Obsidian's app.json.

    Args:
        base_dir: The project base directory.
        root_override: Optional override path to the .obsidian directory (relative to base_dir).

    Returns:
        True if strictLineBreaks is enabled, False if disabled, or None if unavailable.
    """
    if root_override:
        obsidian_dir = (base_dir / root_override).resolve()
    else:
        obsidian_dir = (base_dir / '.obsidian').resolve()

    app_json_path = obsidian_dir / 'app.json'

    try:
        content = app_json_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        lg.warning(f'Obsidian integration enabled but app.json not found: {app_json_path}')
        return None
    except PermissionError:
        lg.warning(f'Obsidian integration enabled but app.json is not readable: {app_json_path}')
        return None

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        lg.warning(f'Obsidian integration enabled but app.json contains malformed JSON: {e}')
        return None

    if 'strictLineBreaks' not in data:
        lg.warning('Obsidian integration enabled but strictLineBreaks not set in app.json')
        return None

    return bool(data['strictLineBreaks'])
