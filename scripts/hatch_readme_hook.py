"""Hatchling metadata hook: build the README long description for packaging.

At build time this rewrites repo-relative Markdown links/images in
``README.md`` to absolute GitHub URLs, so the PyPI long description has
working links (PyPI has no repo tree to resolve relative paths against).
The checked-in ``README.md`` stays relative-link-friendly for GitHub.

The transform is done in-memory via ``scripts/pypi_readme.py`` so there is
no generated file to track and local/dev builds behave identically to CI.
"""

from __future__ import annotations

import importlib.util
import pathlib

from hatchling.metadata.plugin.interface import MetadataHookInterface


def _load_transform(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location(
        'pypi_readme', root / 'scripts' / 'pypi_readme.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.transform


class ReadmeMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict) -> None:
        root = pathlib.Path(self.root)
        transform = _load_transform(root)
        source = (root / 'README.md').read_text(encoding='utf-8')
        metadata['readme'] = {
            'content-type': 'text/markdown',
            'text': transform(source),
        }
