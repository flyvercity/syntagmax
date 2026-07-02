# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-02
# Description: Pandoc integration for converting Markdown to DOCX/PDF.

import logging as lg
import shutil
import subprocess
from pathlib import Path


def check_pandoc() -> bool:
    """Check if pandoc is available in PATH."""
    return shutil.which('pandoc') is not None


def convert(source_md: Path, output_path: Path, output_format: str) -> tuple[bool, str]:
    """
    Convert a Markdown file to the specified format using Pandoc.

    Args:
        source_md: Path to the source Markdown file.
        output_path: Path to the output file.
        output_format: Target format ('docx' or 'pdf').

    Returns:
        A tuple of (success, message). On failure, message includes the exit code
        and stderr output (truncated to 500 chars).
    """
    cmd = ['pandoc', str(source_md), '-o', str(output_path)]
    lg.debug(f'Running Pandoc: {" ".join(cmd)}')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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
