# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-03-22
# Description: Base class for extracting artifacts from Markdown content.

from pathlib import Path
import logging as lg
import re
from typing import Callable
from lark import Lark, Transformer, exceptions
from benedict import benedict

from syntagmax.extractors.extractor import Extractor, ExtractorResult
from syntagmax.config import Config, InputRecord, ExcludeElementConfig
from syntagmax.artifact import ArtifactBuilder, Artifact, Location, UNDEFINED_ID
from syntagmax.blocks import Block, TextBlock, ArtifactBlock, ErrorBlock

_VALID_BLOCK_ID_RE = re.compile(r'^[a-zA-Z0-9_.\-]+$')


def _validate_block_id(id_str: str) -> bool:
    """Check if a block ID contains only valid characters [a-zA-Z0-9_-.]."""
    return bool(_VALID_BLOCK_ID_RE.match(id_str))


# Patterns for detecting Markdown block-level elements
_HEADING_RE = re.compile(r'^\s*#{1,6}\s')
_TABLE_ROW_RE = re.compile(r'^\s*\|')
_UNORDERED_LIST_RE = re.compile(r'^\s*[-*+]\s')
_ORDERED_LIST_RE = re.compile(r'^\s*\d+[.)]\s')
_THEMATIC_BREAK_RE = re.compile(r'^\s*[-*_]{3,}\s*$')
_HTML_BLOCK_RE = re.compile(r'^\s*<')
_FENCE_START_RE = re.compile(r'^\s*```')


def _is_block_element(line_content: str) -> bool:
    """Check if a line (without line ending) is a Markdown block-level element."""
    return bool(
        _HEADING_RE.match(line_content)
        or _TABLE_ROW_RE.match(line_content)
        or _UNORDERED_LIST_RE.match(line_content)
        or _ORDERED_LIST_RE.match(line_content)
        or _THEMATIC_BREAK_RE.match(line_content)
        or _HTML_BLOCK_RE.match(line_content)
    )


def apply_soft_line_breaks(text: str) -> str:
    """Convert single newlines to Markdown hard breaks (trailing two spaces).

    This implements Obsidian's relaxed line break behavior for standard Markdown
    renderers. The transformation is:
    - Code-block-aware: lines inside fenced code blocks are never modified.
    - CRLF-safe: preserves original line endings.
    - Block-syntax-aware: headings, tables, lists, thematic breaks, and HTML blocks
      are never modified.
    - Paragraph-safe: empty/whitespace-only lines and lines preceding them are not modified.

    Args:
        text: The input text content.

    Returns:
        Text with single newlines converted to hard breaks where appropriate.
    """
    if not text:
        return text

    # Split preserving line endings
    lines = text.splitlines(keepends=True)
    if not lines:
        return text

    result: list[str] = []
    in_code_block = False

    for i, line in enumerate(lines):
        # Separate content from line ending
        if line.endswith('\r\n'):
            content = line[:-2]
            ending = '\r\n'
        elif line.endswith('\n'):
            content = line[:-1]
            ending = '\n'
        elif line.endswith('\r'):
            content = line[:-1]
            ending = '\r'
        else:
            # Last line without trailing newline — no transformation needed
            result.append(line)
            continue

        stripped = content.lstrip()

        # Track fenced code block state
        if _FENCE_START_RE.match(content):
            in_code_block = not in_code_block
            result.append(line)
            continue

        # Lines inside code blocks are never modified
        if in_code_block:
            result.append(line)
            continue

        # Empty or whitespace-only lines are never modified
        if not stripped:
            result.append(line)
            continue

        # Check if next line is empty or whitespace-only (preserve paragraph breaks)
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            # Strip line ending from next line for whitespace check
            if next_line.endswith('\r\n'):
                next_content = next_line[:-2]
            elif next_line.endswith('\n'):
                next_content = next_line[:-1]
            elif next_line.endswith('\r'):
                next_content = next_line[:-1]
            else:
                next_content = next_line
            if not next_content.strip():
                result.append(line)
                continue

        # Block-level elements are never modified
        if _is_block_element(content):
            result.append(line)
            continue

        # Already has a hard break (trailing two spaces or backslash)
        if content.endswith('  ') or content.endswith('\\'):
            result.append(line)
            continue

        # Apply transformation: append two spaces before line ending
        result.append(content + '  ' + ending)

    return ''.join(result)


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

    def _NL(self, t):
        return None

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


class MarkdownExtractor(Extractor):
    def __init__(self, config: Config, record: InputRecord, metamodel: dict | None = None):
        super().__init__(config, record, metamodel)
        grammar_path = Path(__file__).parent / 'markdown.lark'
        grammar = grammar_path.read_text(encoding='utf-8')

        # Replace placeholders with actual marker
        marker = self._record.marker
        grammar = grammar.replace('_TOKEN_BEGIN', f'"[{marker}]"i')
        grammar = grammar.replace('_TOKEN_END', f'"[/{marker}]"i')

        self._parser = Lark(grammar, parser='lalr', maybe_placeholders=False)
        self._transformer = MarkdownTransformer()

    def _is_multiple_attr(self, atype: str, attr_name: str) -> bool:
        if not self._metamodel:
            return False
        attrs = self._metamodel.get('artifacts', {}).get(atype, {}).get('attributes', {}).get(attr_name, [])
        if isinstance(attrs, dict):
            attrs = [attrs]
        return any(rule.get('multiple', False) for rule in attrs)

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
                    raw_yaml = segment[yaml_start + 7: yaml_end]
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
                        segment = segment[:yaml_start] + new_yaml_block + segment[yaml_end + 3:]
                    except YAMLParsingError as e:
                        lg.warning(
                            f'Could not round-trip YAML for {artifact.aid}, '
                            f'falling back to regex: {e}'
                        )
                        # Fallback: regex-based id replacement in YAML
                        yaml_block = segment[yaml_start: yaml_end + 3]
                        yaml_block = re.sub(
                            r'^(\s*id:\s*).*$', rf'\g<1>{new_id}',
                            yaml_block, flags=re.MULTILINE
                        )
                        segment = segment[:yaml_start] + yaml_block + segment[yaml_end + 3:]
            else:
                # No YAML block - fallback to regex for YAML if somehow there's inline yaml
                pass

            # Also update [id] format if it exists in the markdown
            segment = re.sub(
                r'\[id\]\s*[a-zA-Z0-9_{}:-]*',
                f'[id] {new_id}', segment, flags=re.IGNORECASE
            )

            # Replace the segment in the lines list
            lines[start_line - 1 : end_line] = [segment]

        filepath.write_text(''.join(lines), encoding='utf-8')

    def update_artifact(self, artifact: Artifact, fields: dict[str, str]):
        from syntagmax.artifact import LineLocation

        if not isinstance(artifact.location, LineLocation):
            return

        if 'id' in fields:
            self.update_artifacts(artifact.location.loc_file, [(artifact, fields['id'])])

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
            segment_lines = lines[start_line - 1: end_line]
            segment = ''.join(segment_lines)

            if target_type == 'attr':
                segment = self._update_yaml_attrs(artifact, segment, attrs_delta, operation, marker, newline)
            elif target_type == 'field':
                segment = self._update_inline_fields(segment, attrs_delta, operation, marker, newline)

            lines[start_line - 1: end_line] = [segment]

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
            raw_yaml = segment[yaml_start + 7: yaml_end]
            # Strip leading newline that follows ```yaml
            if raw_yaml.startswith('\n'):
                raw_yaml = raw_yaml[1:]
            elif raw_yaml.startswith('\r\n'):
                raw_yaml = raw_yaml[2:]

            try:
                modified_yaml = roundtrip_modify_attrs(raw_yaml, attrs_delta, operation)
            except YAMLParsingError as e:
                aid = artifact.aid if hasattr(artifact, 'aid') else 'unknown'
                lg.error(
                    f'Error parsing YAML block in artifact {aid}: {e}'
                    + (f' ({e.details})' if e.details else '')
                )
                return segment

            new_yaml_block = f'```yaml{newline}{modified_yaml.rstrip()}{newline}```'
            segment = segment[:yaml_start] + new_yaml_block + segment[yaml_end + 3:]
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
            pattern = re.compile(
                rf'(?mi)^\[{escaped_name}\][^\r\n]*(?:\r?\n(?!(?:\[|```yaml)).*)*'
            )

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
                    elif end + 1 < len(segment) and segment[end: end + 2] == '\r\n':
                        end += 2
                    segment = segment[:start] + segment[end:]
            elif operation == 'replace':
                if match:
                    # In-place replacement: keep position, replace value
                    new_field = f'[{attr_name}] {attr_value or ""}'
                    segment = segment[:match.start()] + new_field + segment[match.end():]
                else:
                    # Field not found - append
                    segment = self._insert_inline_field(segment, attr_name, attr_value or '', marker, newline)

        return segment

    def _insert_inline_field(
        self, segment: str, name: str, value: str, marker: str, newline: str
    ) -> str:
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

    def _extract_from_markdown(self, filepath: Path, markdown: str, location_builder: Callable[[int, int], Location]) -> ExtractorResult:
        blocks = self._extract_blocks_from_markdown(filepath, markdown, location_builder)
        artifacts = [b.artifact for b in blocks if isinstance(b, ArtifactBlock)]
        errors = [b.message for b in blocks if isinstance(b, ErrorBlock)]
        return artifacts, errors

    def _split_text_block_by_markers(self, text_block: TextBlock) -> list[Block]:
        """Split a TextBlock into marked and unmarked fragments based on configured markers.

        Supports three marker formats (applied as a pipeline):
        1. Paired (closed): [MARKER]content[/MARKER]
        2. Paired (unclosed): [MARKER]content terminated by empty line, next marker, heading, or end-of-string
        3. Line-prefix: [MARKER] content (paragraph terminated by blank line or end-of-string)
           Also handles [MARKER id] identified variants.
        """
        markers = self._record.markers
        if not markers:
            return [text_block]

        escaped = '|'.join(re.escape(m) for m in markers)
        base_offset = text_block.source_offset

        # Pipeline: start with the input block, apply passes to unmarked blocks
        blocks: list[Block] = [text_block]

        # Pass 1: Fully closed paired markers [MARKER]...[/MARKER]
        blocks = self._apply_marker_pass(blocks, self._split_closed_paired, escaped, base_offset)

        # Pass 2: Unclosed paired markers [MARKER]...terminated by empty line/next marker/heading/EOF
        blocks = self._apply_marker_pass(blocks, self._split_unclosed_paired, escaped, base_offset)

        # Pass 3: Line-prefix markers [MARKER] content
        blocks = self._apply_marker_pass(blocks, self._split_line_prefix, escaped, base_offset)

        return blocks if blocks else [text_block]

    def _apply_marker_pass(self, blocks: list[Block], splitter, escaped: str, base_offset: int | None) -> list[Block]:
        """Apply a splitting pass to all unmarked TextBlocks in the list."""
        result: list[Block] = []
        for block in blocks:
            if isinstance(block, TextBlock) and block.marker is None:
                result.extend(splitter(block.content, escaped, block.source_offset))
            else:
                result.append(block)
        return result

    def _split_closed_paired(self, content: str, escaped: str, base_offset: int | None) -> list[Block]:
        """Split by fully closed paired markers [MARKER]...[/MARKER]."""
        paired_pattern = re.compile(rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)\[/\1\]', re.IGNORECASE | re.DOTALL)
        matches = list(paired_pattern.finditer(content))
        if not matches:
            return [TextBlock(content=content, marker=None, source_offset=base_offset)]

        result: list[Block] = []
        pos = 0
        for match in matches:
            before = content[pos:match.start()]
            if before:
                offset = (base_offset + pos) if base_offset is not None else None
                result.append(TextBlock(content=before, marker=None, source_offset=offset))
            marker_name = match.group(1).upper()
            raw_id = match.group(2)
            marker_content = match.group(3)
            tag_offset = (base_offset + match.start()) if base_offset is not None else None

            if raw_id is not None:
                raw_id = raw_id.strip()
                if not _validate_block_id(raw_id):
                    result.append(ErrorBlock(
                        message=f'Invalid block ID "{raw_id}" for marker [{marker_name}] — IDs must match [a-zA-Z0-9_.-]',
                        raw_text=match.group(0),
                    ))
                    pos = match.end()
                    continue
                result.append(TextBlock(content=marker_content, marker=marker_name, id=raw_id, explicit_id=True, source_offset=tag_offset))
            else:
                result.append(TextBlock(content=marker_content, marker=marker_name, source_offset=tag_offset))
            pos = match.end()
        after = content[pos:]
        if after:
            offset = (base_offset + pos) if base_offset is not None else None
            result.append(TextBlock(content=after, marker=None, source_offset=offset))
        return result if result else [TextBlock(content=content, marker=None, source_offset=base_offset)]

    def _split_unclosed_paired(self, content: str, escaped: str, base_offset: int | None) -> list[Block]:
        """Split by unclosed paired markers terminated by empty line, next marker, heading, or EOF."""
        # Lookahead terminates on: double newline, next fragment marker, heading, or end of string
        unclosed_pattern = re.compile(
            rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)(?=\n\s*\n|\n\s*\[(?:{escaped})(?:\s+[^\]]+)?\]|\n\s*#{{1,6}}\s|\Z)',
            re.IGNORECASE | re.DOTALL,
        )
        matches = list(unclosed_pattern.finditer(content))
        if not matches:
            return [TextBlock(content=content, marker=None, source_offset=base_offset)]

        result: list[Block] = []
        pos = 0
        for match in matches:
            before = content[pos:match.start()]
            if before:
                offset = (base_offset + pos) if base_offset is not None else None
                result.append(TextBlock(content=before, marker=None, source_offset=offset))
            marker_name = match.group(1).upper()
            raw_id = match.group(2)
            marker_content = match.group(3).strip()
            tag_offset = (base_offset + match.start()) if base_offset is not None else None

            if raw_id is not None:
                raw_id = raw_id.strip()
                if not _validate_block_id(raw_id):
                    result.append(ErrorBlock(
                        message=f'Invalid block ID "{raw_id}" for marker [{marker_name}] — IDs must match [a-zA-Z0-9_.-]',
                        raw_text=match.group(0),
                    ))
                    # Consume the terminating empty line if present
                    end_pos = match.end()
                    if end_pos < len(content) and content[end_pos] == '\n':
                        remaining = content[end_pos:]
                        empty_match = re.match(r'\n\s*\n', remaining)
                        if empty_match:
                            end_pos += empty_match.end()
                    pos = end_pos
                    continue
                result.append(TextBlock(content=marker_content, marker=marker_name, id=raw_id, explicit_id=True, source_offset=tag_offset))
            else:
                result.append(TextBlock(content=marker_content, marker=marker_name, source_offset=tag_offset))

            # Consume the terminating empty line if present
            end_pos = match.end()
            if end_pos < len(content) and content[end_pos] == '\n':
                # Check if it's an empty line terminator (consume it)
                remaining = content[end_pos:]
                empty_match = re.match(r'\n\s*\n', remaining)
                if empty_match:
                    end_pos += empty_match.end()
            pos = end_pos
        after = content[pos:]
        if after:
            offset = (base_offset + pos) if base_offset is not None else None
            result.append(TextBlock(content=after, marker=None, source_offset=offset))
        return result if result else [TextBlock(content=content, marker=None, source_offset=base_offset)]

    def _split_line_prefix(self, content: str, escaped: str, base_offset: int | None) -> list[Block]:
        """Split by line-prefix markers [MARKER] content at start of paragraph."""
        prefix_pattern = re.compile(
            rf'^\[({escaped})(?:\s+([^\]]+))?\]\s*(.*?)(?=\n\n|\Z)',
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )
        matches = list(prefix_pattern.finditer(content))
        if not matches:
            return [TextBlock(content=content, marker=None, source_offset=base_offset)]

        result: list[Block] = []
        pos = 0
        for match in matches:
            before = content[pos:match.start()]
            if before:
                offset = (base_offset + pos) if base_offset is not None else None
                result.append(TextBlock(content=before, marker=None, source_offset=offset))
            marker_name = match.group(1).upper()
            raw_id = match.group(2)
            marker_content = match.group(3).strip()
            tag_offset = (base_offset + match.start()) if base_offset is not None else None

            if raw_id is not None:
                raw_id = raw_id.strip()
                if not _validate_block_id(raw_id):
                    result.append(ErrorBlock(
                        message=f'Invalid block ID "{raw_id}" for marker [{marker_name}] — IDs must match [a-zA-Z0-9_.-]',
                        raw_text=match.group(0),
                    ))
                    pos = match.end()
                    continue
                result.append(TextBlock(content=marker_content, marker=marker_name, id=raw_id, explicit_id=True, source_offset=tag_offset))
            else:
                result.append(TextBlock(content=marker_content, marker=marker_name, source_offset=tag_offset))
            pos = match.end()
        after = content[pos:]
        if after:
            offset = (base_offset + pos) if base_offset is not None else None
            result.append(TextBlock(content=after, marker=None, source_offset=offset))
        return result if result else [TextBlock(content=content, marker=None, source_offset=base_offset)]

    def _extract_blocks_from_markdown(self, filepath: Path, markdown: str, location_builder: Callable[[int, int], Location] | None = None) -> list[Block]:
        from syntagmax.artifact import LineLocation

        blocks: list[Block] = []
        marker = self._record.marker
        start_marker_re = re.compile(rf'\[{marker}\]', re.IGNORECASE)
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

            # Find segment end — priority: YAML block > [/MARKER] > fallback terminators.
            # Context-aware: fallback terminators (fragment markers, headings, empty lines, EOF)
            # only apply when no explicit [/MARKER] or YAML block is found.
            next_marker_match = start_marker_re.search(markdown, match.end())
            terminator_search_end = next_marker_match.start() if next_marker_match else len(markdown)
            slash_req_match = re.search(
                rf'\[/{marker}\]',
                markdown[start_pos:terminator_search_end],
                re.IGNORECASE,
            )
            slash_req_pos = (start_pos + slash_req_match.start()) if slash_req_match else -1
            # Constrain ```yaml search to within the [/MARKER] boundary to avoid
            # matching literal ```yaml inside requirement content.
            # When [/MARKER] is absent, use the already-computed boundary before the
            # next [MARKER] occurrence to avoid consuming unrelated YAML blocks.
            yaml_search_end = slash_req_pos if slash_req_pos != -1 else terminator_search_end
            yaml_start_pos = markdown.find('```yaml', start_pos, yaml_search_end)
            segment_end = -1

            if yaml_start_pos != -1:
                end_pos = markdown.find('```', yaml_start_pos + 7)
                if end_pos != -1:
                    segment_end = end_pos + 3
            elif slash_req_pos != -1:
                segment_end = slash_req_pos + len(f'[/{marker}]')

            # Context-aware fallback: if no YAML or [/TAG] found, search for
            # fragment markers at BOL, Markdown headings, empty lines, or EOF.
            _fallback_pos_set = False
            if segment_end == -1:
                # Start searching after the first newline following [MARKER]
                # to avoid matching the line break right after the opening tag.
                first_nl = markdown.find('\n', match.end())
                if first_nl != -1 and first_nl < terminator_search_end:
                    fallback_search_start = first_nl + 1
                else:
                    fallback_search_start = match.end()
                fallback_search_region = markdown[fallback_search_start:terminator_search_end]

                # Build fallback terminator regex: fragment marker at BOL, heading at BOL, or empty line
                fallback_patterns = []

                # Fragment markers at beginning of line
                fragment_markers = getattr(self._record, 'markers', None) or []
                if fragment_markers:
                    escaped_markers = '|'.join(re.escape(m) for m in fragment_markers)
                    fallback_patterns.append(rf'^(?:\[(?:{escaped_markers})(?:\s+[^\]]+)?\])')

                # Markdown headings (# followed by space, up to 6 #)
                fallback_patterns.append(r'^#{1,6}\s')

                # Empty line: newline followed by optional whitespace/CR followed by another newline
                # Using a non-MULTILINE approach to correctly handle CRLF
                fallback_patterns.append(r'\n[ \t]*\r?\n')

                fallback_re = re.compile('|'.join(f'({p})' for p in fallback_patterns), re.MULTILINE | re.IGNORECASE)
                fallback_match = fallback_re.search(fallback_search_region)

                if fallback_match:
                    # segment_end is set to position of the fallback match (exclusive of the match itself)
                    fallback_abs_pos = fallback_search_start + fallback_match.start()

                    # For empty lines, consume the empty line(s) when advancing pos
                    if fallback_match.group(len(fallback_patterns)):  # last group = empty line
                        # The empty line pattern \n...\n starts with the \n that ends the last content line.
                        # Include that \n in the segment (parser needs trailing newline).
                        segment_end = fallback_abs_pos + 1
                        # Consume all consecutive blank lines after the segment
                        # Only consume full blank lines (whitespace + newline), NOT leading
                        # indentation of the next non-empty line.
                        consume_end = fallback_search_start + fallback_match.end()
                        while consume_end < len(markdown):
                            # Try to consume a blank line: optional spaces/tabs followed by a newline
                            scan = consume_end
                            while scan < len(markdown) and markdown[scan] in ' \t':
                                scan += 1
                            if scan < len(markdown) and markdown[scan] == '\r':
                                scan += 1
                            if scan < len(markdown) and markdown[scan] == '\n':
                                consume_end = scan + 1
                            else:
                                break
                        pos = consume_end
                        _fallback_pos_set = True
                    else:
                        # Fragment markers and headings are NOT consumed — they're at BOL
                        # segment_end is the start of that line
                        segment_end = fallback_abs_pos
                        pos = fallback_abs_pos
                        _fallback_pos_set = True
                else:
                    # EOF fallback — use everything up to terminator_search_end
                    segment_end = terminator_search_end
                    pos = terminator_search_end
                    _fallback_pos_set = True

            if segment_end == -1:
                # Should not happen given EOF fallback, but guard against it
                start_line = markdown.count('\n', 0, start_pos) + 1
                if yaml_start_pos != -1:
                    error = f'Unclosed YAML block in requirement at line {start_line} in {filepath}'
                else:
                    error = f'Unterminated requirement at line {start_line} in {filepath}'
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
            if _fallback_pos_set and segment and not segment.endswith('\n'):
                segment += '\n'

            # Advance pos: if fallback termination already set pos, use that;
            # otherwise advance past the segment end (YAML/[/TAG] case).
            if not _fallback_pos_set:
                pos = segment_end

            lg.debug(f'Found requirement at line {start_line}, parsing')

            try:
                tree = self._parser.parse(segment)
                req_data = self._transformer.transform(tree)
                req = benedict(req_data)

                contents = req.get_str('req.contents.text')
                fields = req.get_list('req.fields.list')
                yaml_info = req.get('req.yaml')
                yaml_text = yaml_info.get('text') if yaml_info else None

                # NBSP detection
                if '\xa0' in segment:
                    error = f'Non-breaking space (NBSP) detected in requirement at line {start_line} in {filepath}'
                    lg.error(error)
                    blocks.append(ErrorBlock(message=error, raw_text=segment))
                    continue

                if not yaml_text:
                    yaml_dict = benedict({'attrs': {}})
                    yaml_attrs = {}
                else:
                    yaml_dict = benedict.from_yaml(yaml_text)

                    if 'attrs' not in yaml_dict:
                        error = f'Invalid metadata in YAML at line {start_line}'
                        lg.error(error)
                        blocks.append(ErrorBlock(message=error, raw_text=segment))
                        continue
                    yaml_attrs = yaml_dict.get_dict('attrs')

                # Merged dict for ID/AType extraction, YAML takes precedence
                temp_attrs = {
                    **{field.get_str('field.marker'): field.get_str('field.contents.text').strip() for field in fields},
                    **yaml_attrs,
                }

                aid = temp_attrs.get('id')

                if not aid:
                    error = f'Missing ID in metadata at line {start_line}'
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
                    builder.add_field(field_marker, field.get_str('field.contents.text').strip())

                # Add fields found in YAML individually
                for name, value in yaml_attrs.items():
                    if name.lower() in ['id', 'atype']:
                        continue
                    if value is None:
                        continue
                    if isinstance(value, list):
                        for v in value:
                            builder.add_field(name, str(v))
                    elif self._is_multiple_attr(atype, name) and ',' in str(value):
                        for v in str(value).split(','):
                            builder.add_field(name, v.strip())
                    else:
                        builder.add_field(name, str(value))

                # Add contents as a field
                builder.add_field('contents', contents)

                artifact = builder.build()
                if isinstance(artifact, MarkdownArtifact):
                    artifact.yaml_data = yaml_dict
                    for field in fields:
                        artifact.source_metadata[field.get_str('field.marker').lower()] = 'markdown'
                    for name in yaml_attrs.keys():
                        artifact.source_metadata[name.lower()] = 'yaml'

                blocks.append(ArtifactBlock(artifact=artifact, raw_text=segment))

            except (exceptions.ParseError, exceptions.UnexpectedToken) as e:
                lg.exception(e)
                error = f'Parse error in requirement at line {start_line} in {filepath}'
                blocks.append(ErrorBlock(message=error, raw_text=segment))

            except Exception as e:
                lg.exception(e)
                error = f'Error processing requirement at line {start_line} in {filepath}'
                blocks.append(ErrorBlock(message=error, raw_text=segment))

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

        return blocks

    def extract_blocks_from_file(self, filepath: Path) -> list[Block]:
        markdown = filepath.read_text(encoding='utf-8')
        blocks = self._extract_blocks_from_markdown(filepath, markdown)
        return self._apply_element_filters(blocks)

    def _apply_element_filters(self, blocks: list[Block]) -> list[Block]:
        """Apply exclude_elements filtering to TextBlocks."""
        exclude = self._record.exclude_elements
        if not exclude:
            return blocks

        filtered: list[Block] = []
        is_file_start = True

        for block in blocks:
            if isinstance(block, TextBlock):
                content = self._filter_text_content(block.content, is_file_start, exclude)
                is_file_start = False
                if content and content.strip():
                    filtered.append(TextBlock(
                        content=content,
                        marker=block.marker,
                        id=block.id,
                        explicit_id=block.explicit_id,
                        source_offset=block.source_offset,
                    ))
            else:
                is_file_start = False
                filtered.append(block)

        return filtered

    def _filter_text_content(
        self, content: str, is_file_start: bool, exclude: list[ExcludeElementConfig]
    ) -> str:
        """Filter excluded Markdown elements from text content.

        Respects fenced code blocks: lines inside ``` fences are never filtered.
        Supports both LF and CRLF line endings.
        Each element has a mode: only, string, or string-on-start.
        """
        import re as _re

        # Build lookup: element name -> mode
        exclude_map: dict[str, str] = {e.name: e.mode for e in exclude}

        # Handle frontmatter first (operates on entire content, not line-by-line)
        # All modes behave identically for frontmatter (complete removal)
        if is_file_start and 'frontmatter' in exclude_map:
            fm_pattern = _re.compile(r'\A---\r?\n.*?\r?\n---\r?\n', _re.DOTALL)
            content = fm_pattern.sub('', content)

        # If no line-level filters remain, return early
        line_elements = set(exclude_map.keys()) & {'callouts', 'headings', 'horizontal_rules', 'tags'}
        if not line_elements:
            return content

        tags_mode = exclude_map.get('tags')
        callouts_mode = exclude_map.get('callouts')
        headings_mode = exclude_map.get('headings')
        hr_mode = exclude_map.get('horizontal_rules')

        # Obsidian tag pattern
        if tags_mode:
            _tag_pattern = _re.compile(
                r'(?<![^\s([{"\'])[ \t]*'
                r'#(?!(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b)'
                r'[^\d\W][\w\-/]*',
                _re.UNICODE,
            )
            # Code span regex for masking
            _code_span_re = _re.compile(r'(`{1,2})(?:.+?)\1')

        hr_pattern = _re.compile(r'^\s*[-*_]{3,}\s*$')
        callout_only_re = _re.compile(r'^(\s*)>\s?(.*)$')
        heading_only_re = _re.compile(r'^(\s*)#{1,6}\s+(.*)$')

        lines = content.splitlines(keepends=True)
        result: list[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.lstrip()

            # Track fenced code block state
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                continue

            # Lines inside code blocks are always preserved
            if in_code_block:
                result.append(line)
                continue

            # --- Callouts ---
            if callouts_mode and stripped.startswith('>'):
                if callouts_mode == 'only':
                    m = callout_only_re.match(line)
                    if m:
                        text_part = line.rstrip('\r\n')
                        ending = line[len(text_part):]
                        result.append(m.group(1) + m.group(2) + ending)
                    else:
                        result.append(line)
                    continue
                else:
                    # string and string-on-start both remove the line
                    continue

            # --- Headings ---
            if headings_mode and stripped.startswith('#'):
                if headings_mode == 'only':
                    m = heading_only_re.match(line)
                    if m:
                        text_part = line.rstrip('\r\n')
                        ending = line[len(text_part):]
                        result.append(m.group(1) + m.group(2) + ending)
                    else:
                        result.append(line)
                    continue
                else:
                    # string and string-on-start both remove the line
                    continue

            # --- Horizontal rules ---
            if hr_mode and hr_pattern.match(line):
                # All modes remove the line
                continue

            # --- Tags ---
            if tags_mode:
                if tags_mode == 'only':
                    line = self._strip_tags_from_line(line, _tag_pattern)
                elif tags_mode == 'string':
                    # Remove entire line if it contains any tag outside code spans
                    if self._line_has_tag(line, _tag_pattern, _code_span_re):
                        continue
                else:
                    # string-on-start: remove line if first non-ws is a tag; else strip inline
                    if self._line_starts_with_tag(line, _tag_pattern, _code_span_re):
                        continue
                    else:
                        line = self._strip_tags_from_line(line, _tag_pattern)

            result.append(line)

        return ''.join(result)

    def _mask_code_spans(self, line: str, code_span_re: 're.Pattern[str]') -> str:
        """Replace inline code span content with placeholder characters for detection."""
        result = list(line)
        for match in code_span_re.finditer(line):
            for i in range(match.start(), match.end()):
                result[i] = 'X'
        return ''.join(result)

    def _line_has_tag(
        self, line: str, tag_pattern: 're.Pattern[str]', code_span_re: 're.Pattern[str]'
    ) -> bool:
        """Check if a line contains an Obsidian tag outside code spans."""
        masked = self._mask_code_spans(line, code_span_re)
        return bool(tag_pattern.search(masked))

    def _line_starts_with_tag(
        self, line: str, tag_pattern: 're.Pattern[str]', code_span_re: 're.Pattern[str]'
    ) -> bool:
        """Check if the first non-whitespace on a line is an Obsidian tag (outside code spans)."""
        masked = self._mask_code_spans(line, code_span_re)
        stripped = masked.lstrip()
        if not stripped:
            return False
        m = tag_pattern.match(stripped)
        return m is not None and m.start() == 0

    def _strip_tags_from_line(self, line: str, tag_pattern: 're.Pattern[str]') -> str:
        """Strip Obsidian inline tags from a line, preserving inline code spans."""
        import re as _re

        # Split the line into inline-code and non-code segments
        # Match single or double backtick inline code spans
        code_span_re = _re.compile(r'(`{1,2})(?:.+?)\1')

        parts: list[str] = []
        pos = 0

        for match in code_span_re.finditer(line):
            # Process text before the code span
            before = line[pos:match.start()]
            if before:
                before = tag_pattern.sub('', before)
                # Collapse multiple horizontal whitespace into one space
                before = _re.sub(r'[ \t]{2,}', ' ', before)
            parts.append(before)
            # Preserve the code span verbatim
            parts.append(match.group(0))
            pos = match.end()

        # Process remaining text after last code span
        remainder = line[pos:]
        if remainder:
            remainder = tag_pattern.sub('', remainder)
            remainder = _re.sub(r'[ \t]{2,}', ' ', remainder)
        parts.append(remainder)

        return ''.join(parts)
