# SPDX-License-Identifier: MIT

import pytest

from syntagmax.yaml_utils import roundtrip_modify_attrs, YAMLParsingError


class TestRoundtripModifyAttrsOrderPreservation:
    """Tests verifying that key order is preserved during modifications."""

    def test_add_preserves_existing_order(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  title: Sample Requirement\n  status: draft\n  priority: high\n  verify: "test_something"\n'
        result = roundtrip_modify_attrs(raw_yaml, {'owner': 'Alice'}, 'add')

        # Verify order: original keys stay in order, new key appended
        lines = result.strip().split('\n')
        keys = [line.strip().split(':')[0] for line in lines if line.startswith('  ')]
        assert keys == ['id', 'title', 'status', 'priority', 'verify', 'owner']

    def test_replace_preserves_order(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  title: Sample Requirement\n  status: draft\n  priority: high\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')

        lines = result.strip().split('\n')
        keys = [line.strip().split(':')[0] for line in lines if line.startswith('  ')]
        assert keys == ['id', 'title', 'status', 'priority']
        assert 'status: active' in result
        assert 'status: draft' not in result

    def test_delete_preserves_order_of_remaining(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  title: Sample Requirement\n  status: draft\n  priority: high\n  verify: "test_something"\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': None}, 'del')

        lines = result.strip().split('\n')
        keys = [line.strip().split(':')[0] for line in lines if line.startswith('  ')]
        assert keys == ['id', 'title', 'priority', 'verify']
        assert 'status' not in result

    def test_multiple_operations_preserve_order(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  title: Original Title\n  status: draft\n  priority: low\n'
        # Replace multiple attrs at once
        result = roundtrip_modify_attrs(
            raw_yaml,
            {'title': 'New Title', 'priority': 'critical'},
            'replace',
        )

        lines = result.strip().split('\n')
        keys = [line.strip().split(':')[0] for line in lines if line.startswith('  ')]
        assert keys == ['id', 'title', 'status', 'priority']
        assert 'title: New Title' in result
        assert 'priority: critical' in result


class TestRoundtripModifyAttrsComments:
    """Tests verifying that comments are preserved."""

    def test_inline_comments_preserved(self):
        raw_yaml = 'attrs:\n  id: REQ-001  # artifact identifier\n  title: Sample  # human-readable name\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')
        assert '# artifact identifier' in result
        assert '# human-readable name' in result
        assert 'status: active' in result

    def test_block_comments_preserved(self):
        raw_yaml = '# Top-level comment\nattrs:\n  # This is the ID\n  id: REQ-001\n  title: Sample\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'owner': 'Bob'}, 'add')
        assert '# Top-level comment' in result
        assert '# This is the ID' in result
        assert 'owner: Bob' in result


class TestRoundtripModifyAttrsListValues:
    """Tests verifying list values round-trip correctly."""

    def test_block_list_preserved(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  tag:\n    - performance\n    - telemetry\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')
        assert '- performance' in result
        assert '- telemetry' in result
        assert 'status: active' in result

    def test_flow_list_preserved(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  tag: [performance, telemetry]\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')
        # ruamel.yaml preserves flow style
        assert 'performance' in result
        assert 'telemetry' in result
        assert 'status: active' in result

    def test_add_list_value(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'tag': ['safety', 'critical']}, 'add')
        assert 'safety' in result
        assert 'critical' in result


class TestRoundtripModifyAttrsErrorHandling:
    """Tests for error handling with malformed YAML."""

    def test_malformed_yaml_raises_error(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  bad_indent:\n    - not closed\n broken: yes\n'
        with pytest.raises(YAMLParsingError) as exc_info:
            roundtrip_modify_attrs(raw_yaml, {'status': 'draft'}, 'add')
        assert 'Failed to parse YAML block' in str(exc_info.value)

    def test_completely_invalid_yaml(self):
        raw_yaml = '{{{{not yaml at all!!!!'
        with pytest.raises(YAMLParsingError):
            roundtrip_modify_attrs(raw_yaml, {'x': '1'}, 'add')

    def test_scalar_root_raises_error(self):
        """YAML that parses to a scalar should raise YAMLParsingError."""
        raw_yaml = 'just a string value\n'
        with pytest.raises(YAMLParsingError) as exc_info:
            roundtrip_modify_attrs(raw_yaml, {'status': 'draft'}, 'add')
        assert 'not a mapping' in str(exc_info.value)

    def test_sequence_root_raises_error(self):
        """YAML that parses to a sequence should raise YAMLParsingError."""
        raw_yaml = '- item1\n- item2\n'
        with pytest.raises(YAMLParsingError) as exc_info:
            roundtrip_modify_attrs(raw_yaml, {'status': 'draft'}, 'add')
        assert 'not a mapping' in str(exc_info.value)

    def test_attrs_as_list_raises_error(self):
        """attrs: [] should raise YAMLParsingError."""
        raw_yaml = 'attrs:\n  - item1\n  - item2\n'
        with pytest.raises(YAMLParsingError) as exc_info:
            roundtrip_modify_attrs(raw_yaml, {'status': 'draft'}, 'add')
        assert 'not a mapping' in str(exc_info.value)

    def test_attrs_as_scalar_raises_error(self):
        """attrs: some_string should raise YAMLParsingError."""
        raw_yaml = 'attrs: not_a_mapping\n'
        with pytest.raises(YAMLParsingError) as exc_info:
            roundtrip_modify_attrs(raw_yaml, {'status': 'draft'}, 'add')
        assert 'not a mapping' in str(exc_info.value)


class TestRoundtripModifyAttrsMissingAttrs:
    """Tests for missing or null attrs key."""

    def test_missing_attrs_key_initializes(self):
        raw_yaml = 'title: Something\n'
        result = roundtrip_modify_attrs(raw_yaml, {'id': 'REQ-001'}, 'add')
        assert 'attrs:' in result
        assert 'id: REQ-001' in result
        # Original content preserved
        assert 'title: Something' in result

    def test_null_attrs_key_initializes(self):
        raw_yaml = 'attrs:\nother: value\n'
        # In YAML, `attrs:` with nothing after it is null
        result = roundtrip_modify_attrs(raw_yaml, {'id': 'REQ-001'}, 'add')
        assert 'id: REQ-001' in result
        assert 'other: value' in result

    def test_empty_yaml_initializes(self):
        raw_yaml = ''
        result = roundtrip_modify_attrs(raw_yaml, {'id': 'REQ-001'}, 'add')
        assert 'attrs:' in result
        assert 'id: REQ-001' in result


class TestRoundtripModifyAttrsLineEndings:
    """Tests for line ending preservation."""

    def test_lf_line_endings_preserved(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')
        assert '\r\n' not in result
        assert 'status: active\n' in result

    def test_crlf_line_endings_preserved(self):
        raw_yaml = 'attrs:\r\n  id: REQ-001\r\n  status: draft\r\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')
        assert '\r\n' in result
        # Check there's no bare \n (only \r\n)
        normalized = result.replace('\r\n', '')
        assert '\n' not in normalized


class TestRoundtripModifyAttrsOperationSemantics:
    """Tests for add/del/replace operation semantics."""

    def test_add_skips_existing_key(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  status: active\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'draft'}, 'add')
        # Should NOT overwrite existing value
        assert 'status: active' in result
        assert 'status: draft' not in result

    def test_del_nonexistent_key_is_noop(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'nonexistent': None}, 'del')
        assert 'id: REQ-001' in result
        assert 'status: draft' in result

    def test_replace_adds_if_missing(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')
        assert 'status: active' in result

    def test_replace_with_none_removes(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': None}, 'replace')
        assert 'status' not in result
        assert 'id: REQ-001' in result

    def test_quoted_values_preserved(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  verify: "test_something"\n  status: draft\n'
        result = roundtrip_modify_attrs(raw_yaml, {'status': 'active'}, 'replace')
        assert '"test_something"' in result

    def test_integer_value(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  version: 2\n'
        result = roundtrip_modify_attrs(raw_yaml, {'version': 3}, 'replace')
        assert 'version: 3' in result

    def test_boolean_value(self):
        raw_yaml = 'attrs:\n  id: REQ-001\n  derived: false\n'
        result = roundtrip_modify_attrs(raw_yaml, {'derived': True}, 'replace')
        assert 'derived: true' in result
