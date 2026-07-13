# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-02
# Description: Pandoc integration for converting Markdown to DOCX/PDF.

import logging as lg
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from syntagmax.publish_config import PublishConfig


def check_pandoc() -> bool:
    """Check if pandoc is available in PATH."""
    return shutil.which('pandoc') is not None


def convert(source_md: Path, output_path: Path, output_format: str, reference_doc: Path | None = None, resource_path: Path | None = None) -> tuple[bool, str]:
    """
    Convert a Markdown file to the specified format using Pandoc.

    Args:
        source_md: Path to the source Markdown file.
        output_path: Path to the output file.
        output_format: Target format ('docx' or 'pdf').
        reference_doc: Optional path to a reference document (--reference-doc).
            Only applied when output_format is 'docx'.
        resource_path: Optional path for Pandoc's --resource-path flag.
            Tells Pandoc where to find images and other resources.

    Returns:
        A tuple of (success, message). On failure, message includes the exit code
        and stderr output (truncated to 500 chars).
    """
    cmd = ['pandoc', str(source_md), '-o', str(output_path)]

    if reference_doc is not None and output_format == 'docx':
        cmd.extend(['--reference-doc', str(reference_doc)])

    if resource_path is not None:
        cmd.extend(['--resource-path', str(resource_path)])

    lg.debug(f'Running Pandoc: {" ".join(cmd)}')

    try:
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=120)
    except FileNotFoundError:
        msg = 'pandoc executable not found in PATH'
        lg.warning(msg)
        return False, msg
    except subprocess.TimeoutExpired:
        msg = 'pandoc conversion timed out after 120 seconds'
        lg.warning(msg)
        return False, msg

    if result.returncode == 0:
        msg = f'Successfully converted to {output_format}: {output_path}'
        lg.debug(msg)
        return True, msg

    stderr = result.stderr.strip()
    if len(stderr) > 500:
        stderr = stderr[:500] + '...'

    msg = f'pandoc exited with status {result.returncode}'
    if stderr:
        msg += f': {stderr}'

    lg.warning(msg)
    return False, msg


BUNDLED_TEMPLATE = Path(__file__).parent / 'resources' / 'template.dotm'


def resolve_docx_template(pub_config: 'PublishConfig', record_name: str, config_root: Path) -> Path | None:
    """
    Resolve the DOCX reference document template path for a given record.

    Resolution order:
    1. Per-record override in docx_template.overrides
    2. docx_template.default_template
    3. Bundled template.dotm

    Args:
        pub_config: The loaded PublishConfig for the record.
        record_name: Name of the input record being published.
        config_root: Project config root directory (directory containing config.toml).

    Returns:
        Path to the template file, or None if explicitly set to "none".

    Raises:
        FatalError: If a configured template path does not exist.
    """
    from syntagmax.errors import FatalError

    docx_tmpl = pub_config.docx_template

    if docx_tmpl is not None:
        # Step 1: Check per-record override
        override = docx_tmpl.overrides.get(record_name)
        if override is not None:
            if override.lower() == 'none':
                return None
            resolved = config_root / override
            if not resolved.exists():
                raise FatalError([f'DOCX template not found: {resolved} (override for record "{record_name}")'])
            return resolved

        # Step 2: Check default-template
        if docx_tmpl.default_template is not None:
            if docx_tmpl.default_template.lower() == 'none':
                return None
            resolved = config_root / docx_tmpl.default_template
            if not resolved.exists():
                raise FatalError([f'DOCX template not found: {resolved} (default-template)'])
            return resolved

    # Step 3: Fall back to bundled template
    return BUNDLED_TEMPLATE
