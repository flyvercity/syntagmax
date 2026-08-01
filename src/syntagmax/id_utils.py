# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-28
# Description: Shared ID schema compilation and extraction utilities.

import re

_NUM_PATTERN = re.compile(r'\{num(?::(\d+))?\}')


def count_num_macros(schema: str) -> int:
    """Count the number of {num} / {num:N} occurrences in a schema string."""
    return len(_NUM_PATTERN.findall(schema))


def compile_id_schema(schema: str, atype: str) -> re.Pattern:
    """Compile an ID schema into an anchored regex with a capture group.

    Steps:
      1. Replace {atype} with re.escape(atype).
      2. Split the remaining string on {num}/{num:N} boundaries.
      3. Escape each literal segment with re.escape.
      4. Replace {num:N} with (\\d{N,}) and {num} with (\\d+).
      5. Anchor with ^...$.
    """
    # Step 1: replace {atype} with the escaped literal type name
    pattern = schema.replace('{atype}', re.escape(atype))

    # Steps 2-4: split on _NUM_PATTERN boundaries, escape literals, insert groups
    parts: list[str] = []
    last_pos = 0

    for match in _NUM_PATTERN.finditer(pattern):
        # Escape the literal segment before this match
        literal = pattern[last_pos : match.start()]
        parts.append(re.escape(literal))

        # Build the capture group
        padding = match.group(1)
        if padding:
            parts.append(rf'(\d{{{padding},}})')
        else:
            parts.append(r'(\d+)')

        last_pos = match.end()

    # Escape the trailing literal segment
    parts.append(re.escape(pattern[last_pos:]))

    # Step 5: anchor
    return re.compile(f'^{"".join(parts)}$')


def extract_number_from_id(aid: str, schema: str, atype: str) -> int | None:
    """Match aid against the compiled schema and return the extracted number, or None.

    Returns None if the schema has no {num} macro (no capture group) or the ID doesn't match.
    """
    compiled = compile_id_schema(schema, atype)
    m = compiled.match(aid)
    if m and m.groups():
        return int(m.group(1))
    return None
