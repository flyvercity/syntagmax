# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-20
# Description: Marker splitting utilities for Markdown extraction.

import re
from typing import TYPE_CHECKING

from syntagmax.blocks import Block, TextBlock, ErrorBlock
from syntagmax.extractors.markdown_filters import _validate_block_id

if TYPE_CHECKING:
    from syntagmax.config import InputRecord

_HEADING_RE_SPLIT = re.compile(r'^([ ]{0,3}#{1,6}\s)')


class MarkerSplitterMixin:
    """Mixin providing marker-based text block splitting for Markdown extractors."""

    if TYPE_CHECKING:
        _record: 'InputRecord'
        _closed_paired_re: re.Pattern[str] | None
        _unclosed_paired_re: re.Pattern[str] | None
        _line_prefix_re: re.Pattern[str] | None

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

        base_offset = text_block.source_offset

        # Pipeline: start with the input block, apply passes to unmarked blocks
        blocks: list[Block] = [text_block]

        # Pass 1: Fully closed paired markers [MARKER]...[/MARKER]
        blocks = self._apply_marker_pass(blocks, self._split_closed_paired, base_offset)

        # Pass 2: Unclosed paired markers [MARKER]...terminated by empty line/next marker/heading/EOF
        blocks = self._apply_marker_pass(blocks, self._split_unclosed_paired, base_offset)

        # Pass 3: Line-prefix markers [MARKER] content
        blocks = self._apply_marker_pass(blocks, self._split_line_prefix, base_offset)

        return blocks if blocks else [text_block]

    def _apply_marker_pass(self, blocks: list[Block], splitter, base_offset: int | None) -> list[Block]:
        """Apply a splitting pass to all unmarked TextBlocks in the list."""
        result: list[Block] = []
        for block in blocks:
            if isinstance(block, TextBlock) and block.marker is None:
                result.extend(splitter(block.content, block.source_offset))
            else:
                result.append(block)
        return result

    def _split_closed_paired(self, content: str, base_offset: int | None) -> list[Block]:
        """Split by fully closed paired markers [MARKER]...[/MARKER]."""
        paired_pattern = self._closed_paired_re
        if paired_pattern is None:
            return [TextBlock(content=content, marker=None, source_offset=base_offset)]
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
                    result.append(
                        ErrorBlock(
                            message=f'Invalid block ID "{raw_id}" for marker [{marker_name}] — IDs must match [a-zA-Z0-9_.-]',
                            raw_text=match.group(0),
                        )
                    )
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

    def _split_unclosed_paired(self, content: str, base_offset: int | None) -> list[Block]:
        """Split by unclosed paired markers terminated by empty line, next marker, heading, or EOF."""
        unclosed_pattern = self._unclosed_paired_re
        if unclosed_pattern is None:
            return [TextBlock(content=content, marker=None, source_offset=base_offset)]
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
                    result.append(
                        ErrorBlock(
                            message=f'Invalid block ID "{raw_id}" for marker [{marker_name}] — IDs must match [a-zA-Z0-9_.-]',
                            raw_text=match.group(0),
                        )
                    )
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

    def _split_line_prefix(self, content: str, base_offset: int | None) -> list[Block]:
        """Split by line-prefix markers [MARKER] content at start of paragraph."""
        prefix_pattern = self._line_prefix_re
        if prefix_pattern is None:
            return [TextBlock(content=content, marker=None, source_offset=base_offset)]
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
                    result.append(
                        ErrorBlock(
                            message=f'Invalid block ID "{raw_id}" for marker [{marker_name}] — IDs must match [a-zA-Z0-9_.-]',
                            raw_text=match.group(0),
                        )
                    )
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

    def _split_headings(self, blocks: list[Block]) -> list[Block]:
        """Split ATX headings out of unmarked TextBlocks as separate heading blocks.

        Headings are identified by CommonMark rules: at most 3 leading spaces
        followed by 1-6 '#' characters and a space. Headings inside fenced code
        blocks are not split. Whitespace-only text blocks are preserved.
        """
        heading_re = _HEADING_RE_SPLIT
        result: list[Block] = []

        for block in blocks:
            if not isinstance(block, TextBlock) or block.marker is not None:
                result.append(block)
                continue

            lines = block.content.splitlines(keepends=True)
            base_offset = block.source_offset
            accumulator: list[str] = []
            current_offset = base_offset
            acc_offset = base_offset
            in_code_block = False

            for line in lines:
                stripped = line.lstrip()

                # Track fenced code block state
                if stripped.startswith('```'):
                    in_code_block = not in_code_block
                    if not accumulator and current_offset is not None:
                        acc_offset = current_offset
                    accumulator.append(line)
                    if current_offset is not None:
                        current_offset += len(line)
                    continue

                if in_code_block:
                    if not accumulator and current_offset is not None:
                        acc_offset = current_offset
                    accumulator.append(line)
                    if current_offset is not None:
                        current_offset += len(line)
                    continue

                if heading_re.match(line):
                    # Flush preceding text (preserve whitespace-only blocks)
                    if accumulator:
                        text = ''.join(accumulator)
                        result.append(TextBlock(content=text, source_offset=acc_offset))
                        accumulator = []

                    # Emit heading block
                    result.append(TextBlock(content=line, marker='HEADING', source_offset=current_offset))
                    if current_offset is not None:
                        current_offset += len(line)
                    acc_offset = current_offset
                else:
                    if not accumulator and current_offset is not None:
                        acc_offset = current_offset
                    accumulator.append(line)
                    if current_offset is not None:
                        current_offset += len(line)

            # Flush remaining text
            if accumulator:
                text = ''.join(accumulator)
                result.append(TextBlock(content=text, source_offset=acc_offset))

        return result
