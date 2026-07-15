# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-15
# Description: Binary file utilities for the change report command.

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

lg = logging.getLogger(__name__)


@dataclass
class ImageProperties:
    """Properties extracted from an image/binary file."""

    size_bytes: int
    width: int | None = None
    height: int | None = None


def compute_file_hash(path: Path) -> str | None:
    """Compute SHA-256 hash of a file's contents.

    Reads the file in 8KB chunks to handle large files efficiently.

    Args:
        path: Path to the file.

    Returns:
        Hex-encoded SHA-256 digest, or None if the file doesn't exist
        or isn't a regular file.
    """
    if not path.exists() or not path.is_file():
        return None

    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
    except OSError as e:
        lg.warning('Failed to read file for hashing: %s: %s', path, e)
        return None

    return h.hexdigest()


def extract_image_properties(path: Path) -> ImageProperties | None:
    """Extract file size and optional image dimensions.

    Uses Pillow for dimension extraction if available. If Pillow is not
    installed or the file is not a supported image format, returns
    properties with size only (width/height as None).

    Args:
        path: Path to the file.

    Returns:
        ImageProperties with size and optional dimensions, or None if
        the file doesn't exist.
    """
    if not path.exists() or not path.is_file():
        return None

    try:
        size_bytes = path.stat().st_size
    except OSError as e:
        lg.warning('Failed to stat file: %s: %s', path, e)
        return None

    width: int | None = None
    height: int | None = None

    try:
        from PIL import Image

        with Image.open(path) as img:
            width, height = img.size
    except ImportError:
        lg.debug('Pillow not installed; skipping dimension extraction for %s', path)
    except Exception as e:
        lg.debug('Could not extract dimensions from %s: %s', path, e)

    return ImageProperties(size_bytes=size_bytes, width=width, height=height)


def format_file_size(size_bytes: int) -> str:
    """Format a file size in bytes as a human-readable string.

    Uses binary-style thresholds but decimal labels (KB, MB, GB)
    for familiarity.

    Examples:
        format_file_size(512) -> "512 B"
        format_file_size(1536) -> "1.5 KB"
        format_file_size(1048576) -> "1.0 MB"
    """
    if size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.1f} KB'
    elif size_bytes < 1024 * 1024 * 1024:
        return f'{size_bytes / (1024 * 1024):.1f} MB'
    else:
        return f'{size_bytes / (1024 * 1024 * 1024):.1f} GB'
