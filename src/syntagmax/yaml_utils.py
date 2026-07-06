# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-06
# Description: Round-trip YAML editing utilities using ruamel.yaml.
#              Preserves key order, comments, and formatting when modifying attrs.

from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError
from ruamel.yaml.compat import StringIO


class YAMLParsingError(Exception):
    """Raised when a YAML block cannot be parsed by ruamel.yaml."""

    def __init__(self, message: str, details: str | None = None):
        super().__init__(message)
        self.details = details


def roundtrip_modify_attrs(
    raw_yaml: str,
    attrs_delta: dict[str, Any],
    operation: str,
) -> str:
    """Apply a batch of attribute updates (add, del, replace) to raw YAML attrs.

    Preserves key order, comments, and formatting of the YAML block.

    Args:
        raw_yaml: Raw YAML text (without ```yaml fences).
        attrs_delta: Mapping of attribute names to values.
                     For 'del' operation, values are ignored.
                     For 'add'/'replace', value=None means deletion.
        operation: One of 'add', 'del', 'replace'.

    Returns:
        Modified YAML text with the same formatting style.

    Raises:
        YAMLParsingError: If the YAML cannot be parsed.
    """
    yaml = YAML(typ='rt')
    yaml.preserve_quotes = True

    try:
        data = yaml.load(raw_yaml)
    except YAMLError as e:
        raise YAMLParsingError(
            'Failed to parse YAML block',
            details=str(e),
        ) from e

    if data is None:
        data = CommentedMap()
        data['attrs'] = CommentedMap()

    # Validate root is a mapping
    if not isinstance(data, dict):
        raise YAMLParsingError(
            'YAML block root is not a mapping',
            details=f'Expected a mapping, got {type(data).__name__}',
        )

    # Handle missing or null attrs key
    if 'attrs' not in data or data['attrs'] is None:
        data['attrs'] = CommentedMap()

    # Validate attrs is a mapping
    if not isinstance(data['attrs'], dict):
        raise YAMLParsingError(
            'YAML "attrs" key is not a mapping',
            details=f'Expected a mapping, got {type(data["attrs"]).__name__}',
        )

    attrs = data['attrs']

    if operation not in {'add', 'del', 'replace'}:
        raise ValueError(f'Unsupported operation: {operation!r}')

    for attr_name, attr_value in attrs_delta.items():
        if operation == 'add':
            # Only add if not already present
            if attr_name not in attrs:
                attrs[attr_name] = attr_value
        elif operation == 'del':
            # Remove if present
            if attr_name in attrs:
                del attrs[attr_name]
        elif operation == 'replace':
            # Set value if not None, else remove
            if attr_value is not None:
                attrs[attr_name] = attr_value
            else:
                if attr_name in attrs:
                    del attrs[attr_name]

    # Serialize back to string
    stream = StringIO()
    yaml.dump(data, stream)
    result = stream.getvalue()

    # Normalize line endings to match input
    if '\r\n' in raw_yaml:
        result = result.replace('\r\n', '\n').replace('\n', '\r\n')

    # Remove trailing newline added by ruamel if input didn't have one
    if not raw_yaml.endswith('\n') and not raw_yaml.endswith('\r\n'):
        result = result.rstrip('\r\n')

    return result
