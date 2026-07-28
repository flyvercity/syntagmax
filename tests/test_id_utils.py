# SPDX-License-Identifier: MIT

"""Tests for syntagmax.id_utils module."""

from syntagmax.id_utils import compile_id_schema, count_num_macros, extract_number_from_id


class TestCompileIdSchema:
    """Tests for compile_id_schema."""

    def test_num_with_padding_matches_minimum_digits(self):
        pat = compile_id_schema('REQ-{num:3}', 'REQ')
        assert pat.match('REQ-001')
        assert pat.match('REQ-999')

    def test_num_with_padding_matches_more_digits(self):
        pat = compile_id_schema('REQ-{num:3}', 'REQ')
        assert pat.match('REQ-1234')

    def test_num_with_padding_rejects_fewer_digits(self):
        pat = compile_id_schema('REQ-{num:3}', 'REQ')
        assert not pat.match('REQ-01')

    def test_num_with_padding_rejects_wrong_atype(self):
        pat = compile_id_schema('REQ-{num:3}', 'REQ')
        assert not pat.match('SYS-001')

    def test_atype_macro_substitution(self):
        pat = compile_id_schema('{atype}-{num}', 'SYS')
        assert pat.match('SYS-1')
        assert pat.match('SYS-42')

    def test_atype_macro_rejects_wrong_type(self):
        pat = compile_id_schema('{atype}-{num}', 'SYS')
        assert not pat.match('REQ-1')

    def test_regex_special_chars_escaped(self):
        """Dot in schema must be literal, not regex wildcard."""
        pat = compile_id_schema('REQ.{num:3}', 'REQ')
        assert pat.match('REQ.001')
        assert not pat.match('REQX001')


class TestExtractNumberFromId:
    """Tests for extract_number_from_id."""

    def test_extracts_padded_number(self):
        assert extract_number_from_id('REQ-007', 'REQ-{num:3}', 'REQ') == 7

    def test_extracts_larger_number(self):
        assert extract_number_from_id('REQ-1234', 'REQ-{num:3}', 'REQ') == 1234

    def test_returns_none_on_mismatch(self):
        assert extract_number_from_id('INVALID', 'REQ-{num:3}', 'REQ') is None

    def test_returns_none_for_zero_macro_schema(self):
        """Schema with no {num} macro has no capture group — should return None, not crash."""
        assert extract_number_from_id('REQ-FIXED', 'REQ-FIXED', 'REQ') is None


class TestCountNumMacros:
    """Tests for count_num_macros."""

    def test_single_padded_macro(self):
        assert count_num_macros('REQ-{num:3}') == 1

    def test_multiple_macros(self):
        assert count_num_macros('{num}-{num:2}') == 2

    def test_no_macros(self):
        assert count_num_macros('REQ-FIXED') == 0
