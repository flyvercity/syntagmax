# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-09
# Description: Publishing context and image manifest for image-aware publishing.

from __future__ import annotations

import logging as lg
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from syntagmax.config import Config


IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp'})


class ImageManifest:
    """Accumulates image copy operations during rendering.

    Maps source_absolute_path → target_relative_path (e.g. 'images/SYS-diagram.png').
    Provides O(1) deduplication: if the same source is added again, returns existing target.
    """

    def __init__(self):
        self._source_to_target: dict[Path, str] = {}

    def add(self, source: Path, base_dir: Path) -> str:
        """Register an image for copying.

        Args:
            source: Absolute path to the source image file.
            base_dir: Project base directory for computing relative path.

        Returns:
            Target relative path (e.g. 'images/SYS-diagram.png').
        """
        resolved = source.resolve()

        # O(1) dedup: return existing target if already registered
        if resolved in self._source_to_target:
            return self._source_to_target[resolved]

        # Compute flattened target name from relative path
        try:
            rel = resolved.relative_to(base_dir.resolve())
        except ValueError:
            # Should not happen (caller validates containment), but be safe
            rel = Path(resolved.name)

        # Flatten: replace path separators with '-'
        flattened = '-'.join(rel.parts)
        target = f'images/{flattened}'

        self._source_to_target[resolved] = target
        return target

    @property
    def entries(self) -> dict[Path, str]:
        """Return the source → target mapping (read-only view)."""
        return dict(self._source_to_target)

    def __len__(self) -> int:
        return len(self._source_to_target)

    def __bool__(self) -> bool:
        return bool(self._source_to_target)

    def merge(self, other: 'ImageManifest') -> None:
        """Merge another manifest into this one (for multi-record accumulation)."""
        for source, target in other._source_to_target.items():
            if source not in self._source_to_target:
                self._source_to_target[source] = target


@dataclass
class RenderContext:
    """Context passed through the rendering pipeline for image resolution."""

    config: Config
    manifest: ImageManifest = field(default_factory=ImageManifest)
    source_file_path: str | None = None
    _obsidian_attachment_path: str | None = field(default=None, init=False, repr=False)
    _obsidian_attachment_path_loaded: bool = field(default=False, init=False, repr=False)

    @property
    def obsidian_attachment_path(self) -> str | None:
        """Lazily load Obsidian attachment folder path on first access."""
        if not self._obsidian_attachment_path_loaded:
            self._obsidian_attachment_path_loaded = True
            obsidian_cfg = self.config.obsidian_driver_config
            if obsidian_cfg.integration:
                from syntagmax.obsidian_settings import read_obsidian_attachment_path
                self._obsidian_attachment_path = read_obsidian_attachment_path(
                    self.config.base_dir(), obsidian_cfg.root
                )
        return self._obsidian_attachment_path


def _is_remote_url(path: str) -> bool:
    """Check if a path is a remote URL."""
    return path.startswith(('http://', 'https://', '//'))


def _is_within_base_dir(resolved: Path, base_dir: Path) -> bool:
    """Check that a resolved path resides within the project workspace."""
    try:
        resolved.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def resolve_image_to_manifest(
    image_ref: str,
    context: RenderContext,
    is_obsidian: bool,
) -> str | None:
    """Resolve an image reference to a manifest target path.

    Args:
        image_ref: The image reference (filename for Obsidian, relative path for standard).
        context: The current render context.
        is_obsidian: True if this is an Obsidian wiki-link reference (filename-only lookup).

    Returns:
        Target relative path (e.g. 'images/SYS-diagram.png') or None if unresolvable/unsafe.
    """
    base_dir = context.config.base_dir()

    if is_obsidian:
        target_filename = image_ref.strip()

        # O(1) check: look in Obsidian attachment folder first
        attachment_path = context.obsidian_attachment_path
        if attachment_path is not None:
            # Resolve note-relative paths (starting with './' or equal to '.')
            if attachment_path == '.' or attachment_path.startswith('./'):
                if context.source_file_path:
                    source_dir = PurePosixPath(context.source_file_path).parent
                    folder = (base_dir / Path(str(source_dir)) / attachment_path).resolve()
                else:
                    folder = None
            else:
                folder = (base_dir / attachment_path).resolve()

            if folder is not None:
                candidate = folder / target_filename
                if candidate.is_file():
                    if not _is_within_base_dir(candidate, base_dir):
                        lg.warning(f'Attachment folder image escapes project workspace: {candidate}')
                        return None
                    return context.manifest.add(candidate, base_dir)

        # O(N) fallback: vault-wide filename search across all input record filepaths
        for record in context.config.input_records():
            for filepath in record.filepaths:
                if filepath.name == target_filename:
                    resolved = filepath.resolve()
                    if not _is_within_base_dir(resolved, base_dir):
                        lg.warning(f'Image path escapes project workspace: {filepath}')
                        return None
                    return context.manifest.add(filepath.absolute(), base_dir)

        lg.warning(f'Cannot resolve Obsidian image reference: {image_ref}')
        return None
    else:
        # Standard markdown: resolve relative to source file's directory
        decoded_ref = urllib.parse.unquote(image_ref)

        if context.source_file_path is None:
            lg.warning(f'Cannot resolve image path without source file context: {image_ref}')
            return None

        # source_file_path is relative to base_dir (e.g. 'SYS/SYS-001.md')
        source_dir = PurePosixPath(context.source_file_path).parent
        # Resolve the image path relative to the source file's directory
        image_posix = PurePosixPath(decoded_ref)
        resolved_rel = source_dir / image_posix

        # Normalise (resolve ..) and convert to absolute
        resolved = (base_dir / Path(str(resolved_rel))).resolve()

        if not _is_within_base_dir(resolved, base_dir):
            lg.warning(f'Image path escapes project workspace: {image_ref}')
            return None

        if not resolved.exists():
            lg.warning(f'Image file not found: {resolved} (from reference: {image_ref})')
            return None

        return context.manifest.add(resolved, base_dir)
