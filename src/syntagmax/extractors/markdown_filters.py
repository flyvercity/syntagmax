# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-20
# Description: Element filtering and text processing utilities for Markdown extraction.

import re
from typing import TYPE_CHECKING

from syntagmax.blocks import Block, TextBlock

if TYPE_CHECKING:
    from syntagmax.config import InputRecord, Config, ExcludeElementConfig

_VALID_BLOCK_ID_RE = re.compile(r'^[a-zA-Z0-9_.\-]+$')

# Patterns for detecting Markdown block-level elements
_HEADING_RE = re.compile(r'^\s*#{1,6}\s')
_TABLE_ROW_RE = re.compile(r'^\s*\|')
_UNORDERED_LIST_RE = re.compile(r'^\s*[-*+]\s')
_ORDERED_LIST_RE = re.compile(r'^\s*\d+[.)]\s')
_THEMATIC_BREAK_RE = re.compile(r'^\s*[-*_]{3,}\s*$')
_HTML_BLOCK_RE = re.compile(r'^\s*<')
_FENCE_START_RE = re.compile(r'^\s*```')

# Module-level pre-compiled static regexes for filtering
_FRONTMATTER_PATTERN = re.compile(r'\A---\r?\n.*?\r?\n---\r?\n', re.DOTALL)
_TAG_PATTERN = re.compile(
    r'(?<![^\s([{"\'])[ \t]*'
    r'#(?!(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b)'
    r'[^\d\W][\w\-/]*',
    re.UNICODE,
)
_CODE_SPAN_RE = re.compile(r'(`{1,2})(?:.+?)\1')
_HR_PATTERN = re.compile(r'^\s*[-*_]{3,}\s*$')
_CALLOUT_ONLY_RE = re.compile(r'^(\s*)>\s?(.*)$')
_HEADING_ONLY_RE = re.compile(r'^(\s*)#{1,6}\s+(.*)$')
_MULTIPLE_WS_RE = re.compile(r'[ \t]{2,}')


def _validate_block_id(id_str: str) -> bool:
    """Check if a block ID contains only valid characters [a-zA-Z0-9_-.]."""
    return bool(_VALID_BLOCK_ID_RE.match(id_str))


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


class ElementFilterMixin:
    """Mixin providing element filtering capabilities for Markdown extractors."""

    if TYPE_CHECKING:
        _record: 'InputRecord'
        _config: 'Config'

    def _apply_element_filters(self, blocks: list[Block]) -> list[Block]:
        """Apply exclude_elements filtering to TextBlocks."""
        exclude = self._record.exclude_elements
        if not exclude:
            return blocks

        # Determine headings exclusion mode (if configured)
        headings_mode: str | None = None
        for e in exclude:
            if e.name == 'headings':
                headings_mode = e.mode
                break

        filtered: list[Block] = []
        is_file_start = True

        for block in blocks:
            if isinstance(block, TextBlock):
                # Handle pre-split HEADING blocks
                if block.marker == 'HEADING' and headings_mode:
                    is_file_start = False
                    if headings_mode in ('string', 'string-on-start'):
                        # Drop the heading block entirely
                        continue
                    elif headings_mode == 'only':
                        # Strip # prefix, convert to plain text block
                        heading_only_re = _HEADING_ONLY_RE
                        m = heading_only_re.match(block.content.rstrip('\r\n'))
                        if m:
                            ending = block.content[len(block.content.rstrip('\r\n')):]
                            content = m.group(1) + m.group(2) + ending
                        else:
                            content = block.content
                        if content and content.strip():
                            filtered.append(
                                TextBlock(
                                    content=content,
                                    marker=None,
                                    id=block.id,
                                    explicit_id=block.explicit_id,
                                    source_offset=block.source_offset,
                                )
                            )
                    continue

                content = self._filter_text_content(block.content, is_file_start, exclude)
                is_file_start = False
                if content and content.strip():
                    filtered.append(
                        TextBlock(
                            content=content,
                            marker=block.marker,
                            id=block.id,
                            explicit_id=block.explicit_id,
                            source_offset=block.source_offset,
                        )
                    )
            else:
                is_file_start = False
                filtered.append(block)

        return filtered

    def _filter_text_content(self, content: str, is_file_start: bool, exclude: list['ExcludeElementConfig']) -> str:
        """Filter excluded Markdown elements from text content.

        Respects fenced code blocks: lines inside ``` fences are never filtered.
        Supports both LF and CRLF line endings.
        Each element has a mode: only, string, or string-on-start.
        """
        # Build lookup: element name -> mode
        exclude_map: dict[str, str] = {e.name: e.mode for e in exclude}

        # Handle frontmatter first (operates on entire content, not line-by-line)
        # All modes behave identically for frontmatter (complete removal)
        if is_file_start and 'frontmatter' in exclude_map:
            content = _FRONTMATTER_PATTERN.sub('', content)

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
            _tag_pattern = _TAG_PATTERN
            # Code span regex for masking
            _code_span_re = _CODE_SPAN_RE

        hr_pattern = _HR_PATTERN
        callout_only_re = _CALLOUT_ONLY_RE
        heading_only_re = _HEADING_ONLY_RE

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

    def _line_has_tag(self, line: str, tag_pattern: 're.Pattern[str]', code_span_re: 're.Pattern[str]') -> bool:
        """Check if a line contains an Obsidian tag outside code spans."""
        masked = self._mask_code_spans(line, code_span_re)
        return bool(tag_pattern.search(masked))

    def _line_starts_with_tag(self, line: str, tag_pattern: 're.Pattern[str]', code_span_re: 're.Pattern[str]') -> bool:
        """Check if the first non-whitespace on a line is an Obsidian tag (outside code spans)."""
        masked = self._mask_code_spans(line, code_span_re)
        stripped = masked.lstrip()
        if not stripped:
            return False
        m = tag_pattern.match(stripped)
        return m is not None and m.start() == 0

    def _strip_tags_from_line(self, line: str, tag_pattern: 're.Pattern[str]') -> str:
        """Strip Obsidian inline tags from a line, preserving inline code spans."""
        # Split the line into inline-code and non-code segments
        # Match single or double backtick inline code spans
        code_span_re = _CODE_SPAN_RE

        parts: list[str] = []
        pos = 0

        for match in code_span_re.finditer(line):
            # Process text before the code span
            before = line[pos:match.start()]
            if before:
                before = tag_pattern.sub('', before)
                # Collapse multiple horizontal whitespace into one space
                before = _MULTIPLE_WS_RE.sub(' ', before)
            parts.append(before)
            # Preserve the code span verbatim
            parts.append(match.group(0))
            pos = match.end()

        # Process remaining text after last code span
        remainder = line[pos:]
        if remainder:
            remainder = tag_pattern.sub('', remainder)
            remainder = _MULTIPLE_WS_RE.sub(' ', remainder)
        parts.append(remainder)

        return ''.join(parts)
