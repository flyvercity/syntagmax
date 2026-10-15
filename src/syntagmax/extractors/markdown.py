# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-22
# Description: Base class for extracting artifacts from Markdown content.

import functools
from pathlib import Path
import logging as lg
import os
import re
import tempfile
from typing import Any, Callable
from benedict import benedict
from lark import Lark, Transformer, exceptions

from syntagmax.extractors.extractor import Extractor
from syntagmax.config import Config, InputRecord
from syntagmax.artifact import ArtifactBuilder, Artifact, Location, UNDEFINED_ID
from syntagmax.blocks import Block, TextBlock, ArtifactBlock, ErrorBlock

from syntagmax.extractors.markdown_filters import (
    ElementFilterMixin,
    apply_soft_line_breaks as apply_soft_line_breaks,  # noqa: F401 — re-exported
)
from syntagmax.extractors.markdown_markers import MarkerSplitterMixin
from syntagmax.i18n import _


# OPTIMIZATION: Module-level caching of Lark base grammar and compiled Lark parser instances by record marker
_GRAMMAR_PATH = Path(__file__).parent / 'markdown.lark'
_BASE_GRAMMAR = _GRAMMAR_PATH.read_text(encoding='utf-8')


@functools.lru_cache(maxsize=32)
def _get_lark_parser(marker: str) -> Lark:
    grammar = _BASE_GRAMMAR.replace('_TOKEN_BEGIN', f'"[{marker}]"i').replace('_TOKEN_END', f'"[/{marker}]"i')
    return Lark(grammar, parser='lalr', maybe_placeholders=False)


class MarkdownArtifact(Artifact):
    def __init__(self, config: Config):
        super().__init__(config)
        self.yaml_data: benedict | None = None
        self.source_metadata: dict[str, str] = {}


class MarkdownTransformer(Transformer):
    def AID(self, t):
        return str(t).lower()

    def yaml_block(self, t):
        # yaml_block: _YAML_BEGIN [YAML_CONTENT] _YAML_END
        # children: [YAML_CONTENT]
        return {'text': str(t[0]) if t else '', 'type': 'yaml'}

    def terminator(self, t):
        # terminator: yaml_block | _REQ_END
        # If yaml_block matches, t[0] is its result.
        # If _REQ_END matches, t is empty because _ tokens are ignored.
        if not t:
            return {'type': 'slash_req'}
        return t[0]

    def contents(self, t):
        return {'text': ''.join(str(c) for c in t) if t else ''}

    def field(self, t):
        # field: _LSQB AID _RSQB [FIELD_TEXT] _NL FIELD_CONT*
        # children: AID, [FIELD_TEXT], [FIELD_CONT...]
        marker = str(t[0])
        parts = [str(c).strip() for c in t[1:] if str(c).strip()]
        text = '\n'.join(parts)
        return {'field': {'marker': marker, 'contents': {'text': text}}}

    def req(self, t):
        # req: _REQ_BEGIN _NL? [contents] field* [terminator]
        # children: [contents], field*, [terminator]
        contents_text = ''
        all_fields = []
        terminator = None

        # Check if the last child is a valid terminator
        if t and isinstance(t[-1], dict) and 'type' in t[-1]:
            terminator = t[-1]
            children = t[:-1]
        else:
            children = list(t)

        for child in children:
            if isinstance(child, dict):
                if 'text' in child:
                    contents_text = child['text']
                elif 'field' in child:
                    all_fields.append(child)

        return {
            'req': {
                'contents': {'text': contents_text},
                'fields': {'list': all_fields},
                'yaml': terminator if terminator and terminator.get('type') == 'yaml' else None,
            }
        }



class MarkdownExtractor(MarkerSplitterMixin, ElementFilterMixin, Extractor):
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        super().__init__(config, record, metamodel)
        marker = self._record.marker
        self._parser = _get_lark_parser(marker)
        self._transformer = MarkdownTransformer()

        # Pre-compile marker-specific and record-specific regexes
        self._start_marker_re = re.compile(rf'\[{marker}\]', re.IGNORECASE)
        self._slash_req_re = re.compile(rf'\[/{marker}\]', re.IGNORECASE)

        markers = self._record.markers
        if markers:
            escaped = '|'.join(re.escape(m) for m in markers)
            self._closed_paired_re = re.compile(rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)\[/\1\]', re.IGNORECASE | re.DOTALL)
            self._unclosed_paired_re = re.compile(
                rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)(?=\n\s*\n|\n\s*\[(?:{escaped})(?:\s+[^\]]+)?\]|\n\s*#{{1,6}}\s|\Z)', re.IGNORECASE | re.DOTALL
            )
            self._line_prefix_re = re.compile(rf'^\[({escaped})(?:\s+([^\]]+))?\]\s*(.*?)(?=\n\n|\Z)', re.IGNORECASE | re.DOTALL | re.MULTILINE)

            fallback_patterns = [rf'^(?:\[(?:{escaped})(?:\s+[^\]]+)?\])', r'^#{1,6}\s', r'\n[ \t]*\r?\n']
            self._fallback_re = re.compile('|'.join(f'({p})' for p in fallback_patterns), re.MULTILINE | re.IGNORECASE)
            self._fallback_num_patterns = len(fallback_patterns)
        else:
            self._closed_paired_re = None
            self._unclosed_paired_re = None
            self._line_prefix_re = None

            fallback_patterns = [r'^#{1,6}\s', r'\n[ \t]*\r?\n']
            self._fallback_re = re.compile('|'.join(f'({p})' for p in fallback_patterns), re.MULTILINE | re.IGNORECASE)
            self._fallback_num_patterns = len(fallback_patterns)

    def _is_multiple_attr(self, atype: str, attr_name: str) -> bool:
        # OPTIMIZATION: Cache whether an attribute is marked as multiple in the metamodel
        cache_key = (atype, attr_name)
        if cache_key in self._is_multiple_cache:
            return self._is_multiple_cache[cache_key]

        if not self._metamodel:
            res = False
        else:
            attrs = self._metamodel.get('artifacts', {}).get(atype, {}).get('attributes', {}).get(attr_name, [])
            if isinstance(attrs, dict):
                attrs = [attrs]
            res = any(rule.get('multiple', False) for rule in attrs)

        self._is_multiple_cache[cache_key] = res
        return res


    def update_artifacts(self, loc_file: str, updates: list[tuple[Artifact, str]]):
        """Renumber artifact IDs in a file. Uses round-trip YAML to preserve attr order."""
        from syntagmax.artifact import LineLocation
        from syntagmax.yaml_utils import roundtrip_modify_attrs, YAMLParsingError

        # Read the file
        filepath = self._config.base_dir() / loc_file
        text = filepath.read_text(encoding='utf-8')
        lines = text.splitlines(keepends=True)

        # Apply updates in reverse order of line numbers to avoid offset shifts
        updates.sort(key=lambda u: u[0].location.loc_lines[0], reverse=True)  # type: ignore

        for artifact, new_id in updates:
            if not isinstance(artifact.location, LineLocation):
                continue

            start_line, end_line = artifact.location.loc_lines
            segment_lines = lines[start_line - 1 : end_line]
            segment = ''.join(segment_lines)

            # Update YAML block using round-trip editing if present
            yaml_start = segment.find('```yaml')
            if yaml_start != -1:
                yaml_end = segment.find('```', yaml_start + 7)
                if yaml_end != -1:
                    raw_yaml = segment[yaml_start + 7 : yaml_end]
                    # Strip leading newline
                    if raw_yaml.startswith('\n'):
                        raw_yaml = raw_yaml[1:]
                    elif raw_yaml.startswith('\r\n'):
                        raw_yaml = raw_yaml[2:]

                    # Detect newline style for this segment
                    newline = '\r\n' if '\r\n' in segment else '\n'

                    try:
                        modified_yaml = roundtrip_modify_attrs(raw_yaml, {'id': new_id}, 'replace')
                        new_yaml_block = f'```yaml{newline}{modified_yaml.rstrip()}{newline}```'
                        segment = segment[:yaml_start] + new_yaml_block + segment[yaml_end + 3 :]
                    except YAMLParsingError as e:
                        lg.warning(f'Could not round-trip YAML for {artifact.aid}, falling back to regex: {e}')
                        # Fallback: regex-based id replacement in YAML
                        yaml_block = segment[yaml_start : yaml_end + 3]
                        yaml_block = re.sub(r'^(\s*id:\s*).*$', rf'\g<1>{new_id}', yaml_block, flags=re.MULTILINE)
                        segment = segment[:yaml_start] + yaml_block + segment[yaml_end + 3 :]
            else:
                # No YAML block - fallback to regex for YAML if somehow there's inline yaml
                pass

            # Also update [id] format if it exists in the markdown
            segment = re.sub(r'\[id\]\s*[a-zA-Z0-9_{}:-]*', f'[id] {new_id}', segment, flags=re.IGNORECASE)

            # Replace the segment in the lines list
            lines[start_line - 1 : end_line] = [segment]

        filepath.write_text(''.join(lines), encoding='utf-8')

    def update_artifact_attributes(
        self,
        loc_file: str,
        updates: list[tuple[Artifact, dict[str, str | None], str]],
        target_type: str = 'attr',
    ) -> str:
        """Apply attribute updates to artifacts in a file. Returns modified content as string.

        Each update is (artifact, {attr_name: value_or_None}, operation).
        operation: 'add', 'del', 'replace'. value=None means deletion.
        target_type: 'attr' (YAML attrs block) or 'field' (inline [FIELD] markers).
        """
        from syntagmax.artifact import LineLocation

        filepath = self._config.base_dir() / loc_file
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            text = f.read()

        # Detect line endings (newline='' preserves original newlines)

        newline = '\r\n' if '\r\n' in text else '\n'

        lines = text.splitlines(keepends=True)
        marker = self._record.marker

        # Sort updates in reverse line order to avoid offset drift
        updates.sort(key=lambda u: u[0].location.loc_lines[0], reverse=True)  # type: ignore

        for artifact, attrs_delta, operation in updates:
            if not isinstance(artifact.location, LineLocation):
                continue

            start_line, end_line = artifact.location.loc_lines
            segment_lines = lines[start_line - 1 : end_line]
            segment = ''.join(segment_lines)

            if target_type == 'attr':
                segment = self._update_yaml_attrs(artifact, segment, attrs_delta, operation, marker, newline)
            elif target_type == 'field':
                segment = self._update_inline_fields(segment, attrs_delta, operation, marker, newline)

            lines[start_line - 1 : end_line] = [segment]

        return ''.join(lines)

    def _update_yaml_attrs(
        self,
        artifact: Artifact,
        segment: str,
        attrs_delta: dict[str, str | None],
        operation: str,
        marker: str,
        newline: str,
    ) -> str:
        """Update YAML attrs block within an artifact segment.

        Uses round-trip YAML parsing to preserve key order, comments, and formatting.
        Note: The in-memory MarkdownArtifact.yaml_data is NOT synchronized after editing.
        This is intentional since the CLI executes a single command and exits.
        """
        from syntagmax.yaml_utils import roundtrip_modify_attrs, YAMLParsingError

        yaml_start = segment.find('```yaml')
        yaml_end = -1
        if yaml_start != -1:
            yaml_end = segment.find('```', yaml_start + 7)

        if yaml_start != -1 and yaml_end != -1:
            # Extract raw YAML (after ```yaml newline, before closing ```)
            raw_yaml = segment[yaml_start + 7 : yaml_end]
            # Strip leading newline that follows ```yaml
            if raw_yaml.startswith('\n'):
                raw_yaml = raw_yaml[1:]
            elif raw_yaml.startswith('\r\n'):
                raw_yaml = raw_yaml[2:]

            try:
                modified_yaml = roundtrip_modify_attrs(raw_yaml, attrs_delta, operation)
            except YAMLParsingError as e:
                aid = artifact.aid if hasattr(artifact, 'aid') else 'unknown'
                lg.error(f'Error parsing YAML block in artifact {aid}: {e}' + (f' ({e.details})' if e.details else ''))
                return segment

            new_yaml_block = f'```yaml{newline}{modified_yaml.rstrip()}{newline}```'
            segment = segment[:yaml_start] + new_yaml_block + segment[yaml_end + 3 :]
        else:
            # No YAML block exists - create one from scratch using ruamel
            try:
                initial_yaml = f'attrs:{newline}'
                modified_yaml = roundtrip_modify_attrs(initial_yaml, attrs_delta, operation)
            except YAMLParsingError as e:
                aid = artifact.aid if hasattr(artifact, 'aid') else 'unknown'
                lg.error(f'Error creating YAML block for artifact {aid}: {e}')
                return segment

            new_yaml_block = f'```yaml{newline}{modified_yaml.rstrip()}{newline}```'

            slash_pos = segment.rfind(f'[/{marker}]')
            if slash_pos != -1:
                segment = segment[:slash_pos] + newline + new_yaml_block + newline + segment[slash_pos:]
            else:
                segment = segment.rstrip() + newline + newline + new_yaml_block + newline

        return segment


    def _update_inline_fields(
        self,
        segment: str,
        attrs_delta: dict[str, str | None],
        operation: str,
        marker: str,
        newline: str,
    ) -> str:
        """Update inline [FIELD] markers within an artifact segment."""
        for attr_name, attr_value in attrs_delta.items():
            # Multiline-safe regex: matches [name] line and any continuation lines
            escaped_name = re.escape(attr_name)
            pattern = re.compile(rf'(?mi)^\[{escaped_name}\][^\r\n]*(?:\r?\n(?!(?:\[|```yaml)).*)*')

            match = pattern.search(segment)

            if operation == 'add':
                if not match:
                    # Append before closing marker
                    segment = self._insert_inline_field(segment, attr_name, attr_value or '', marker, newline)
            elif operation == 'del':
                if match:
                    # Remove the matched field (and trailing newline if present)
                    start, end = match.start(), match.end()
                    # Also consume trailing newline
                    if end < len(segment) and segment[end] == '\n':
                        end += 1
                    elif end + 1 < len(segment) and segment[end : end + 2] == '\r\n':
                        end += 2
                    segment = segment[:start] + segment[end:]
            elif operation == 'replace':
                if match:
                    # In-place replacement: keep position, replace value
                    new_field = f'[{attr_name}] {attr_value or ""}'
                    segment = segment[: match.start()] + new_field + segment[match.end() :]
                else:
                    # Field not found - append
                    segment = self._insert_inline_field(segment, attr_name, attr_value or '', marker, newline)

        return segment

    def _insert_inline_field(self, segment: str, name: str, value: str, marker: str, newline: str) -> str:
        """Insert an inline field before [/MARKER] or before the YAML block."""
        new_field_line = f'[{name}] {value}'

        # Try to insert before [/MARKER]
        slash_pos = segment.rfind(f'[/{marker}]')
        if slash_pos != -1:
            # Ensure preceding newline
            insert_pos = slash_pos
            if insert_pos > 0 and segment[insert_pos - 1] != '\n':
                new_field_line = newline + new_field_line
            return segment[:insert_pos] + new_field_line + newline + segment[insert_pos:]

        # Try to insert before ```yaml
        yaml_pos = segment.find('```yaml')
        if yaml_pos != -1:
            insert_pos = yaml_pos
            if insert_pos > 0 and segment[insert_pos - 1] != '\n':
                new_field_line = newline + new_field_line
            return segment[:insert_pos] + new_field_line + newline + segment[insert_pos:]

        # Fallback: append at end
        return segment.rstrip() + newline + new_field_line + newline


    # --- Write seam (R3) ---------------------------------------------------

    def _atomic_write(self, target: Path, content: str) -> None:
        """Write ``content`` to ``target`` atomically (E1).

        Writes to a temporary file in the *same directory* and then
        ``os.replace()``s it over the target, so a mid-write failure never
        corrupts the source file. Uses ``encoding='utf-8', newline=''`` to
        preserve line endings exactly, matching ``edit_attrs``.
        """
        target = Path(target)
        tmp_dir = target.parent
        fd = tempfile.NamedTemporaryFile(
            mode='w', dir=tmp_dir, delete=False, encoding='utf-8', newline='', suffix='.tmp'
        )
        tmp_name = fd.name
        try:
            with fd:
                fd.write(content)
            os.replace(tmp_name, target)
        except BaseException:
            # Clean up the temp file on any failure; never leave it behind.
            try:
                os.remove(tmp_name)
            except OSError:
                pass
            raise

    def _resolve_within_root(self, target_file: str) -> Path:
        """Resolve ``target_file`` (relative to base dir) and verify it lies
        within the artifact base directory (path-traversal guard, E1).

        Anchored on ``config.base_dir()`` — the directory input artifacts are
        actually resolved against (``root_dir`` joined with the configured
        ``base``) — so a project whose ``config.toml`` lives in a subdirectory
        (e.g. ``.syntagmax`` with ``base = ".."``) can still create/delete
        files in its input tree. Traversal outside the base (``../..``) is
        still rejected.

        Raises ``ValueError`` on any traversal attempt.
        """
        base = self._config.base_dir().resolve()
        candidate = Path(target_file)
        resolved = (base / candidate).resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            raise ValueError(f'target_file "{target_file}" resolves outside the project base ({base})')
        return resolved

    def edit_artifact(
        self,
        artifact: Artifact,
        *,
        fields: dict[str, str | None] | None = None,
        body: str | None = None,
    ) -> None:
        """Edit an existing artifact's YAML fields and/or body.

        A ``None`` field value deletes that YAML attribute key; a non-``None``
        value sets/replaces it. When ``body`` is given, it replaces the
        artifact's ``contents``.
        """
        from syntagmax.artifact import LineLocation

        if not isinstance(artifact.location, LineLocation):
            raise ValueError('edit_artifact requires an artifact with a line-based location')

        loc_file = artifact.location.filepath()
        target = self._config.base_dir() / loc_file

        content: str | None = None

        if fields:
            # Split into replace (non-None) and delete (None) deltas, since
            # update_artifact_attributes applies a single operation per call.
            replace_delta = {k: v for k, v in fields.items() if v is not None}
            delete_delta = {k: None for k, v in fields.items() if v is None}

            if replace_delta:
                content = self.update_artifact_attributes(loc_file, [(artifact, replace_delta, 'replace')], 'attr')
            if delete_delta:
                if content is not None:
                    # Persist the replace pass first so the delete pass reads it.
                    self._atomic_write(target, content)
                content = self.update_artifact_attributes(loc_file, [(artifact, delete_delta, 'del')], 'attr')

        if body is not None:
            content = self._set_artifact_body(artifact, content, target, body)

        if content is not None:
            self._atomic_write(target, content)

    def _read_text(self, target: Path) -> str:
        with open(target, 'r', encoding='utf-8', newline='') as f:
            return f.read()

    def _set_artifact_body(self, artifact: 'Artifact', content: str | None, target: Path, body: str) -> str:
        """Replace the body/contents text of the artifact's segment."""
        from syntagmax.artifact import LineLocation

        assert isinstance(artifact.location, LineLocation)
        text = content if content is not None else self._read_text(target)
        newline = '\r\n' if '\r\n' in text else '\n'
        lines = text.splitlines(keepends=True)
        start_line, end_line = artifact.location.loc_lines
        segment_lines = lines[start_line - 1 : end_line]
        segment = ''.join(segment_lines)
        marker = self._record.marker

        # The body is the text between the opening [MARKER] line and the first
        # field marker / YAML block / closing marker.
        open_re = re.compile(rf'\[{re.escape(marker)}\][^\r\n]*\r?\n', re.IGNORECASE)
        m = open_re.search(segment)
        if not m:
            # No opening marker found in the segment; leave unchanged.
            return text
        body_start = m.end()

        # Find where the body ends: first field marker, ```yaml, or closing marker.
        rest = segment[body_start:]
        end_candidates = []
        field_m = re.search(r'(?mi)^\[[^\]/][^\]]*\]', rest)
        if field_m:
            end_candidates.append(field_m.start())
        yaml_pos = rest.find('```yaml')
        if yaml_pos != -1:
            end_candidates.append(yaml_pos)
        slash_pos = rest.lower().find(f'[/{marker.lower()}]')
        if slash_pos != -1:
            end_candidates.append(slash_pos)
        body_end_rel = min(end_candidates) if end_candidates else len(rest)
        body_end = body_start + body_end_rel

        new_body_text = body
        if not new_body_text.endswith(('\n', '\r\n')):
            new_body_text += newline
        new_segment = segment[:body_start] + new_body_text + segment[body_end:]

        lines[start_line - 1 : end_line] = [new_segment]
        return ''.join(lines)

    def create_artifact(
        self,
        *,
        target_file: str,
        atype: str,
        aid: str,
        fields: dict,
        body: str,
    ) -> Artifact:
        """Create a new artifact in ``target_file``.

        ``aid`` is required (non-``None``). Missing parent directories are
        created, and ``target_file`` is validated to resolve within
        ``config.root_dir`` (traversal raises ``ValueError``).
        """
        if aid is None:
            raise ValueError('create_artifact requires a non-None aid in this phase')

        target = self._resolve_within_root(target_file)
        target.parent.mkdir(parents=True, exist_ok=True)

        marker = self._record.marker

        # Determine newline: preserve an existing file's style, else default LF.
        if target.exists():
            existing = self._read_text(target)
            newline = '\r\n' if '\r\n' in existing else '\n'
            prefix = existing
            if prefix and not prefix.endswith(('\n', '\r\n')):
                prefix += newline
            prefix += newline
        else:
            newline = '\n'
            existing = ''
            prefix = ''

        # Build the YAML attrs block via the ruamel-based round-trip helper so
        # keys and values are safely quoted/escaped (a newline or YAML-special
        # value can no longer inject attributes or corrupt the frontmatter).
        from syntagmax.yaml_utils import roundtrip_modify_attrs

        attrs_delta: dict[str, Any] = {'id': aid}
        if atype:
            attrs_delta['atype'] = atype
        for key, value in fields.items():
            if key.lower() in ('id', 'atype', 'contents'):
                continue
            attrs_delta[key] = value

        initial_yaml = f'attrs:{newline}'
        modified_yaml = roundtrip_modify_attrs(initial_yaml, attrs_delta, 'add')
        yaml_block = f'```yaml{newline}{modified_yaml.rstrip()}{newline}```'

        body_text = body or ''
        segment_parts = [f'[{marker}]{newline}']
        if body_text:
            segment_parts.append(body_text)
            if not body_text.endswith(('\n', '\r\n')):
                segment_parts.append(newline)
        # The YAML attrs block terminates the requirement (no [/MARKER] needed;
        # a closing marker would end the requirement before the YAML terminator).
        segment_parts.append(yaml_block)
        segment_parts.append(newline)
        segment = ''.join(segment_parts)

        content = prefix + segment
        self._atomic_write(target, content)

        # Re-extract the created artifact from the fresh file.
        artifacts, _errors = self.extract_from_file(target)
        for a in artifacts:
            if a.aid == aid:
                return a
        # Should not happen; return the last-parsed artifact if present.
        if artifacts:
            return artifacts[-1]
        raise ValueError(f'Failed to re-extract created artifact "{aid}" from {target_file}')

    def delete_artifact(self, artifact: Artifact) -> None:
        """Delete an artifact.

        Removes the artifact's marked fragment; when it was the file's only
        artifact, the underlying file is deleted.
        """
        from syntagmax.artifact import LineLocation

        if not isinstance(artifact.location, LineLocation):
            raise ValueError('delete_artifact requires an artifact with a line-based location')

        loc_file = artifact.location.filepath()
        target = self._config.base_dir() / loc_file

        # Count artifacts currently in the file.
        artifacts, _errors = self.extract_from_file(target)
        if len(artifacts) <= 1:
            # Sole artifact: remove the whole file.
            if target.exists():
                os.remove(target)
            return

        text = self._read_text(target)
        lines = text.splitlines(keepends=True)
        start_line, end_line = artifact.location.loc_lines
        # Remove the fragment lines.
        del lines[start_line - 1 : end_line]
        new_content = ''.join(lines)
        self._atomic_write(target, new_content)


    def _find_segment_boundary(
        self,
        markdown: str,
        start_pos: int,
        match_end: int,
        terminator_search_end: int,
        marker: str,
    ) -> tuple[int, int, bool, int]:
        """Find segment end and return (segment_end, next_pos, fallback_pos_set, yaml_start_pos)."""
        slash_req_match = self._slash_req_re.search(markdown[start_pos:terminator_search_end])
        slash_req_pos = (start_pos + slash_req_match.start()) if slash_req_match else -1

        yaml_search_end = slash_req_pos if slash_req_pos != -1 else terminator_search_end
        yaml_start_pos = markdown.find('```yaml', start_pos, yaml_search_end)
        segment_end = -1
        next_pos = -1
        fallback_pos_set = False

        if yaml_start_pos != -1:
            end_pos = markdown.find('```', yaml_start_pos + 7)
            if end_pos != -1:
                segment_end = end_pos + 3
        elif slash_req_pos != -1:
            segment_end = slash_req_pos + len(f'[/{marker}]')

        if segment_end == -1:
            # Context-aware fallback
            first_nl = markdown.find('\n', match_end)
            if first_nl != -1 and first_nl < terminator_search_end:
                fallback_search_start = first_nl + 1
            else:
                fallback_search_start = match_end
            fallback_search_region = markdown[fallback_search_start:terminator_search_end]

            fallback_match = self._fallback_re.search(fallback_search_region)

            if fallback_match:
                fallback_abs_pos = fallback_search_start + fallback_match.start()
                if fallback_match.group(self._fallback_num_patterns):  # last group = empty line
                    segment_end = fallback_abs_pos + 1
                    consume_end = fallback_search_start + fallback_match.end()
                    while consume_end < len(markdown):
                        scan = consume_end
                        while scan < len(markdown) and markdown[scan] in ' \t':
                            scan += 1
                        if scan < len(markdown) and markdown[scan] == '\r':
                            scan += 1
                        if scan < len(markdown) and markdown[scan] == '\n':
                            consume_end = scan + 1
                        else:
                            break
                    next_pos = consume_end
                    fallback_pos_set = True
                else:
                    segment_end = fallback_abs_pos
                    next_pos = fallback_abs_pos
                    fallback_pos_set = True
            else:
                segment_end = terminator_search_end
                next_pos = terminator_search_end
                fallback_pos_set = True

        return segment_end, next_pos, fallback_pos_set, yaml_start_pos


    def _process_segment(
        self,
        segment: str,
        start_line: int,
        end_line: int,
        filepath: Path,
        location_builder: Callable[[int, int], Location],
    ) -> Block:
        """Process a segment of markdown, parse it, and build either an ArtifactBlock or an ErrorBlock."""
        try:
            tree = self._parser.parse(segment)
            req_data = self._transformer.transform(tree)
            req = benedict(req_data)

            contents = req.get('req.contents.text') or ''
            fields = req.get_list('req.fields.list')
            yaml_info = req.get('req.yaml')
            yaml_text = yaml_info.get('text') if yaml_info else None

            # NBSP detection
            if '\xa0' in segment:
                error = _("Non-breaking space (NBSP) detected in requirement at line {line} in {file}").format(line=start_line, file=filepath)
                lg.error(error)
                return ErrorBlock(message=error, raw_text=segment)

            if not yaml_text:
                yaml_dict = benedict({'attrs': {}})
                yaml_attrs = {}
            else:
                yaml_dict = benedict.from_yaml(yaml_text)

                if 'attrs' not in yaml_dict:
                    error = _("Invalid metadata in YAML at line {line}").format(line=start_line)
                    lg.error(error)
                    return ErrorBlock(message=error, raw_text=segment)
                yaml_attrs = yaml_dict.get_dict('attrs')

            # Merged dict for ID/AType extraction, YAML takes precedence
            temp_attrs = {
                **{field.get_str('field.marker'): (field.get('field.contents.text') or '').strip() for field in fields},
                **yaml_attrs,
            }

            aid = temp_attrs.get('id')

            if not aid:
                error = _("Missing ID in metadata at line {line}").format(line=start_line)
                lg.warning(error)
                aid = UNDEFINED_ID

            if 'atype' in temp_attrs:
                lg.warning(
                    f'Overriding default atype with `atype` attribute in {filepath} at line {start_line}. '
                    'To change the type for all artifacts in this source, use the `atype` setting in config.toml.'
                )

            atype = temp_attrs.get('atype') or self._record.default_atype

            builder = ArtifactBuilder(
                config=self._config,
                ArtifactClass=MarkdownArtifact,
                driver=self.driver(),
                location=location_builder(start_line, end_line),
                metamodel=self._metamodel,
                record=self._record,
            )

            builder.add_id(aid, atype)
            builder.add_field('id', aid)

            # Add fields found in markdown individually
            for field in fields:
                field_marker = field.get_str('field.marker')
                if field_marker.lower() in ['id', 'atype']:
                    continue
                builder.add_field(field_marker, (field.get('field.contents.text') or '').strip())

            # Add fields found in YAML individually
            for name, value in yaml_attrs.items():
                if name.lower() in ['id', 'atype']:
                    continue
                if value is None:
                    continue
                if isinstance(value, list):
                    for v in value:
                        builder.add_field(name, self._yaml_value_to_str(v, atype, name))
                elif self._is_multiple_attr(atype, name) and ',' in str(value):
                    for v in str(value).split(','):
                        builder.add_field(name, v.strip())
                else:
                    builder.add_field(name, self._yaml_value_to_str(value, atype, name))

            # Add contents as a field
            builder.add_field('contents', contents)

            artifact = builder.build()
            if isinstance(artifact, MarkdownArtifact):
                artifact.yaml_data = yaml_dict
                for field in fields:
                    artifact.source_metadata[field.get_str('field.marker').lower()] = 'markdown'
                for name in yaml_attrs.keys():
                    artifact.source_metadata[name.lower()] = 'yaml'

            return ArtifactBlock(artifact=artifact, raw_text=segment)

        except (exceptions.ParseError, exceptions.UnexpectedToken) as e:
            lg.exception(e)
            error = _("Parse error in requirement at line {line} in {file}").format(line=start_line, file=filepath)
            return ErrorBlock(message=error, raw_text=segment)

        except Exception as e:
            lg.exception(e)
            error = _("Error processing requirement at line {line} in {file}").format(line=start_line, file=filepath)
            return ErrorBlock(message=error, raw_text=segment)


    def _extract_blocks_from_markdown(self, filepath: Path, markdown: str, location_builder: Callable[[int, int], Location] | None = None) -> list[Block]:
        from syntagmax.artifact import LineLocation

        blocks: list[Block] = []
        marker = self._record.marker
        start_marker_re = self._start_marker_re
        pos = 0

        if location_builder is None:
            loc_file = self._config.derive_path(filepath)

            def location_builder(start, end):
                return LineLocation(loc_file=loc_file, loc_lines=(start, end))

        while True:
            match = start_marker_re.search(markdown, pos)
            if not match:
                break

            start_pos = match.start()

            # Capture text before this segment
            text_before = markdown[pos:start_pos]
            if text_before:
                blocks.append(TextBlock(content=text_before, source_offset=pos))

            next_marker_match = start_marker_re.search(markdown, match.end())
            terminator_search_end = next_marker_match.start() if next_marker_match else len(markdown)

            # Find segment end
            segment_end, next_pos, fallback_pos_set, yaml_start_pos = self._find_segment_boundary(
                markdown, start_pos, match.end(), terminator_search_end, marker
            )

            if segment_end == -1:
                # Should not happen given EOF fallback, but guard against it
                start_line = markdown.count('\n', 0, start_pos) + 1
                if yaml_start_pos != -1:
                    error = _("Unclosed YAML block in requirement at line {line} in {file}").format(line=start_line, file=filepath)
                else:
                    error = _("Unterminated requirement at line {line} in {file}").format(line=start_line, file=filepath)
                lg.error(error)
                raw = markdown[start_pos : match.end()]
                blocks.append(ErrorBlock(message=error, raw_text=raw))
                pos = match.end()
                continue

            segment = markdown[start_pos:segment_end]
            start_line = markdown.count('\n', 0, start_pos) + 1
            end_line = markdown.count('\n', 0, segment_end) + 1

            # Ensure segment ends with a newline for the Lark parser
            # (only needed for fallback-terminated segments that may lack one, e.g. EOF)
            if fallback_pos_set and segment and not segment.endswith('\n'):
                segment += '\n'

            # Advance pos: if fallback termination already set pos, use that;
            # otherwise advance past the segment end (YAML/[/TAG] case).
            if fallback_pos_set:
                pos = next_pos
            else:
                pos = segment_end

            lg.debug(f'Found requirement at line {start_line}, parsing')

            block = self._process_segment(segment, start_line, end_line, filepath, location_builder)
            blocks.append(block)

        # Capture trailing text
        text_after = markdown[pos:]
        if text_after:
            blocks.append(TextBlock(content=text_after, source_offset=pos))

        # Post-process: split TextBlocks by fragment markers
        if self._record.markers:
            split_blocks: list[Block] = []
            for block in blocks:
                if isinstance(block, TextBlock) and block.marker is None:
                    split_blocks.extend(self._split_text_block_by_markers(block))
                else:
                    split_blocks.append(block)
            blocks = split_blocks

        # Post-process: split headings into separate TextBlocks
        blocks = self._split_headings(blocks)

        return blocks

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        markdown = filepath.read_text(encoding='utf-8')
        blocks = self._extract_blocks_from_markdown(filepath, markdown)
        return self._apply_element_filters(blocks)
