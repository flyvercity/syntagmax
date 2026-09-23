"""Transform the repository README into a PyPI-friendly version.

PyPI renders the long description as a standalone page with no repository
tree behind it, so repo-relative Markdown links (``docs/reference/foo.md``)
and relative image references break. GitHub, by contrast, resolves those
paths against the repo. This module rewrites repo-relative links and images
to absolute GitHub URLs so the same source README works in both places.

Rules:
- Links ``[text](target)`` whose target is relative (not ``http(s)://``,
  ``mailto:`` or a pure ``#anchor``) are rewritten to ``blob/<ref>/<target>``.
- Images ``![alt](target)`` with a relative target are rewritten to the raw
  content host (``raw.githubusercontent.com/.../<ref>/<target>``) so they
  display inline on PyPI.
- Absolute URLs and in-page anchors are left untouched.
"""

from __future__ import annotations

import re

# Repository coordinates. Kept here (rather than parsed from pyproject) to keep
# the transform dependency-free and usable as a plain script.
GITHUB_REPO = 'flyvercity/syntagmax'
DEFAULT_REF = 'main'

_BLOB_BASE = f'https://github.com/{GITHUB_REPO}/blob/{DEFAULT_REF}/'
_RAW_BASE = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{DEFAULT_REF}/'

# Matches Markdown links/images: optional leading '!' (image), the [label],
# then (target). We only capture the target and whether it was an image.
_LINK_RE = re.compile(r'(!?)\[([^\]]*)\]\(([^)]+)\)')


def _is_relative(target: str) -> bool:
    """Return True if the link target should be rewritten to an absolute URL."""
    stripped = target.strip()
    if not stripped:
        return False
    if stripped.startswith('#'):
        return False  # in-page anchor
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', stripped):
        return False  # has a scheme: http:, https:, mailto:, etc.
    if stripped.startswith('//'):
        return False  # protocol-relative URL
    return True


def _rewrite_target(target: str, is_image: bool) -> str:
    base = _RAW_BASE if is_image else _BLOB_BASE
    return base + target.lstrip('./')


def transform(markdown: str) -> str:
    """Rewrite repo-relative links/images in *markdown* to absolute GitHub URLs."""

    def repl(match: re.Match[str]) -> str:
        bang, label, target = match.group(1), match.group(2), match.group(3)
        if not _is_relative(target):
            return match.group(0)
        new_target = _rewrite_target(target, is_image=bool(bang))
        return f'{bang}[{label}]({new_target})'

    return _LINK_RE.sub(repl, markdown)


def main() -> None:
    import pathlib
    import sys

    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'README.md')
    dst = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'README.pypi.md')
    dst.write_text(transform(src.read_text(encoding='utf-8')), encoding='utf-8')
    print(f'Wrote {dst} from {src}')


if __name__ == '__main__':
    main()
