# SPDX-License-Identifier: MIT
"""Tests for the attribute_presence feature in publishing."""

import logging
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from pydantic import ValidationError

from syntagmax.publish_config import PublishConfig, TableSection, TextSection, load_publish_config
from syntagmax.metamodel import evaluate_condition, is_attribute_mandatory
from syntagmax.publish import render_block, should_render_attribute
from syntagmax.blocks import ArtifactBlock
from syntagmax.artifact import Artifact


# --- Fixtures ---


@pytest.fixture
def simple_metamodel():
    """A simple metamodel with mandatory, optional, and conditional attributes."""
    return {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'presence': 'mandatory', 'type_info': {'type': 'string'}, 'condition': None}],
                    'contents': [{'presence': 'mandatory', 'type_info': {'type': 'string'}, 'condition': None}],
                    'parent': [{'presence': 'mandatory', 'type_info': {'type': 'reference', 'to_parent': True},
                                'condition': {'anchor': 'derive', 'negated': True}}],
                    'derive': [{'presence': 'optional', 'type_info': {'type': 'boolean'}, 'condition': None}],
                    'status': [{'presence': 'mandatory', 'type_info': {'type': 'enum', 'allowed': ['draft', 'active']}, 'condition': None}],
                    'priority': [{'presence': 'optional', 'type_info': {'type': 'integer'}, 'condition': None}],
                },
            },
        },
        'traces': {},
    }


@pytest.fixture
def custom_boolean_metamodel():
    """A metamodel with custom boolean values."""
    return {
        'artifacts': {
            'SRS': {
                'artifact_name': 'SRS',
                'attributes': {
                    'id': [{'presence': 'mandatory', 'type_info': {'type': 'string'}, 'condition': None}],
                    'contents': [{'presence': 'mandatory', 'type_info': {'type': 'string'}, 'condition': None}],
                    'derived': [{'presence': 'optional', 'type_info': {
                        'type': 'boolean',
                        'custom_values': {'true': ['yes', 'si'], 'false': ['no', 'nein']},
                    }, 'condition': None}],
                    'parent': [{'presence': 'mandatory', 'type_info': {'type': 'reference', 'to_parent': True},
                                'condition': {'anchor': 'derived', 'negated': True}}],
                },
            },
        },
        'traces': {},
    }


def _make_artifact(aid, fields, atype='REQ'):
    """Create a mock Artifact with given fields."""
    a = MagicMock(spec=Artifact)
    a.aid = aid
    a.atype = atype
    a.fields = fields
    a.location = None  # No file location (not a sidecar artifact)
    return a


# --- PublishConfig and TableSection model tests ---


class TestAttributePresenceConfig:
    def test_default_attribute_presence_is_values_only(self):
        config = PublishConfig()
        assert config.attribute_presence == 'values-only'

    def test_attribute_presence_via_alias(self):
        config = PublishConfig.model_validate({'attribute-presence': 'mandatory'})
        assert config.attribute_presence == 'mandatory'

    def test_attribute_presence_via_field_name(self):
        config = PublishConfig.model_validate({'attribute_presence': 'all'})
        assert config.attribute_presence == 'all'

    def test_attribute_presence_invalid_raises_validation_error(self):
        with pytest.raises(ValidationError):
            PublishConfig.model_validate({'attribute-presence': 'invalid'})

    def test_attribute_presence_all_values(self):
        for mode in ('all', 'mandatory', 'values-only'):
            config = PublishConfig.model_validate({'attribute-presence': mode})
            assert config.attribute_presence == mode

    def test_table_section_attribute_presence_default_none(self):
        sec = TableSection.model_validate({'type': 'table', 'attributes': [{'id': {'alias': 'ID'}}]})
        assert sec.attribute_presence is None

    def test_table_section_attribute_presence_via_alias(self):
        sec = TableSection.model_validate({
            'type': 'table',
            'attribute-presence': 'all',
            'attributes': [{'id': {'alias': 'ID'}}],
        })
        assert sec.attribute_presence == 'all'

    def test_table_section_attribute_presence_via_field_name(self):
        sec = TableSection.model_validate({
            'type': 'table',
            'attribute_presence': 'mandatory',
            'attributes': [{'id': {'alias': 'ID'}}],
        })
        assert sec.attribute_presence == 'mandatory'

    def test_table_section_attribute_presence_invalid_raises(self):
        with pytest.raises(ValidationError):
            TableSection.model_validate({
                'type': 'table',
                'attribute-presence': 'wrong',
                'attributes': [{'id': {'alias': 'ID'}}],
            })

    def test_text_section_does_not_accept_attribute_presence(self):
        """TextSection has extra='forbid', so attribute-presence is rejected."""
        with pytest.raises(ValidationError):
            TextSection.model_validate({
                'type': 'text',
                'mode': 'block',
                'attribute-presence': 'all',
                'attributes': [{'contents': {'alias': 'Content'}}],
            })

    def test_attribute_presence_from_yaml(self, tmp_path):
        yaml_content = """
attribute-presence: mandatory
render:
  REQ:
    - type: table
      attribute-presence: all
      attributes:
        - id:
            alias: "ID"
"""
        p = tmp_path / 'publish.yaml'
        p.write_text(yaml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.yaml'), tmp_path)
        assert config.attribute_presence == 'mandatory'
        assert config.render['REQ'][0].attribute_presence == 'all'

    def test_attribute_presence_from_toml(self, tmp_path):
        toml_content = """
"attribute-presence" = "all"

[[render.REQ]]
type = "table"
"attribute-presence" = "values-only"

[[render.REQ.attributes]]
[render.REQ.attributes.id]
alias = "ID"
"""
        p = tmp_path / 'publish.toml'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.toml'), tmp_path)
        assert config.attribute_presence == 'all'
        assert config.render['REQ'][0].attribute_presence == 'values-only'


# --- evaluate_condition tests ---


class TestEvaluateCondition:
    def test_no_condition_returns_true(self, simple_metamodel):
        result = evaluate_condition({'derive': 'yes'}, 'REQ', None, simple_metamodel)
        assert result is True

    def test_negated_condition_anchor_absent(self, simple_metamodel):
        """'if not derive' when derive is absent -> condition holds (True)."""
        condition = {'anchor': 'derive', 'negated': True}
        result = evaluate_condition({}, 'REQ', condition, simple_metamodel)
        assert result is True

    def test_negated_condition_anchor_falsy(self, simple_metamodel):
        """'if not derive' when derive='no' (default falsy) -> condition holds (True)."""
        condition = {'anchor': 'derive', 'negated': True}
        result = evaluate_condition({'derive': 'no'}, 'REQ', condition, simple_metamodel)
        assert result is True

    def test_negated_condition_anchor_truthy(self, simple_metamodel):
        """'if not derive' when derive='yes' -> condition does NOT hold (False)."""
        condition = {'anchor': 'derive', 'negated': True}
        result = evaluate_condition({'derive': 'yes'}, 'REQ', condition, simple_metamodel)
        assert result is False

    def test_positive_condition_anchor_truthy(self, simple_metamodel):
        """'if derive' when derive='true' -> condition holds (True)."""
        condition = {'anchor': 'derive', 'negated': False}
        result = evaluate_condition({'derive': 'true'}, 'REQ', condition, simple_metamodel)
        assert result is True

    def test_positive_condition_anchor_absent(self, simple_metamodel):
        """'if derive' when derive is absent -> condition does NOT hold (False)."""
        condition = {'anchor': 'derive', 'negated': False}
        result = evaluate_condition({}, 'REQ', condition, simple_metamodel)
        assert result is False

    def test_custom_boolean_truthy(self, custom_boolean_metamodel):
        """Custom boolean 'yes'/'si' evaluates as truthy."""
        condition = {'anchor': 'derived', 'negated': True}
        # 'if not derived' when derived='si' -> si is truthy -> condition is False
        result = evaluate_condition({'derived': 'si'}, 'SRS', condition, custom_boolean_metamodel)
        assert result is False

    def test_custom_boolean_falsy(self, custom_boolean_metamodel):
        """Custom boolean 'no'/'nein' evaluates as falsy."""
        condition = {'anchor': 'derived', 'negated': True}
        # 'if not derived' when derived='nein' -> nein is falsy -> condition is True
        result = evaluate_condition({'derived': 'nein'}, 'SRS', condition, custom_boolean_metamodel)
        assert result is True

    def test_empty_string_is_falsy(self, simple_metamodel):
        condition = {'anchor': 'derive', 'negated': True}
        result = evaluate_condition({'derive': ''}, 'REQ', condition, simple_metamodel)
        assert result is True

    def test_list_truthy_when_non_empty(self, simple_metamodel):
        condition = {'anchor': 'derive', 'negated': False}
        result = evaluate_condition({'derive': ['a', 'b']}, 'REQ', condition, simple_metamodel)
        assert result is True

    def test_list_falsy_when_empty(self, simple_metamodel):
        condition = {'anchor': 'derive', 'negated': False}
        result = evaluate_condition({'derive': []}, 'REQ', condition, simple_metamodel)
        assert result is False


# --- is_attribute_mandatory tests ---


class TestIsAttributeMandatory:
    def test_unconditional_mandatory(self, simple_metamodel):
        result = is_attribute_mandatory('status', 'REQ', {}, simple_metamodel)
        assert result is True

    def test_optional_attribute(self, simple_metamodel):
        result = is_attribute_mandatory('priority', 'REQ', {}, simple_metamodel)
        assert result is False

    def test_conditional_mandatory_condition_holds(self, simple_metamodel):
        """parent is mandatory if not derive; derive absent -> mandatory."""
        result = is_attribute_mandatory('parent', 'REQ', {}, simple_metamodel)
        assert result is True

    def test_conditional_mandatory_condition_not_holds(self, simple_metamodel):
        """parent is mandatory if not derive; derive='yes' -> not mandatory."""
        result = is_attribute_mandatory('parent', 'REQ', {'derive': 'yes'}, simple_metamodel)
        assert result is False

    def test_no_metamodel_returns_false(self):
        result = is_attribute_mandatory('status', 'REQ', {}, None)
        assert result is False

    def test_atype_not_in_metamodel(self, simple_metamodel):
        result = is_attribute_mandatory('status', 'UNKNOWN', {}, simple_metamodel)
        assert result is False

    def test_attribute_not_in_metamodel(self, simple_metamodel):
        result = is_attribute_mandatory('nonexistent', 'REQ', {}, simple_metamodel)
        assert result is False

    def test_id_attribute_is_mandatory(self, simple_metamodel):
        result = is_attribute_mandatory('id', 'REQ', {}, simple_metamodel)
        assert result is True


# --- should_render_attribute tests ---


class TestShouldRenderAttribute:
    def test_with_value_always_renders(self, simple_metamodel):
        """All modes render when value is present."""
        for mode in ('all', 'mandatory', 'values-only'):
            assert should_render_attribute('priority', 'high', mode, 'REQ', {}, simple_metamodel) is True

    def test_values_only_no_value_skips(self, simple_metamodel):
        assert should_render_attribute('priority', None, 'values-only', 'REQ', {}, simple_metamodel) is False

    def test_all_no_value_renders(self, simple_metamodel):
        assert should_render_attribute('priority', None, 'all', 'REQ', {}, simple_metamodel) is True

    def test_mandatory_mode_mandatory_attr_no_value_renders(self, simple_metamodel):
        assert should_render_attribute('status', None, 'mandatory', 'REQ', {}, simple_metamodel) is True

    def test_mandatory_mode_optional_attr_no_value_skips(self, simple_metamodel):
        assert should_render_attribute('priority', None, 'mandatory', 'REQ', {}, simple_metamodel) is False

    def test_mandatory_mode_conditional_mandatory_renders(self, simple_metamodel):
        """parent mandatory if not derive; derive absent -> should render."""
        assert should_render_attribute('parent', None, 'mandatory', 'REQ', {}, simple_metamodel) is True

    def test_mandatory_mode_conditional_not_mandatory_skips(self, simple_metamodel):
        """parent mandatory if not derive; derive='yes' -> should NOT render."""
        assert should_render_attribute('parent', None, 'mandatory', 'REQ', {'derive': 'yes'}, simple_metamodel) is False


# --- Rendering integration tests ---


class TestTableSectionRendering:
    """Integration tests for render_block with attribute_presence on table sections."""

    def _make_pub_config(self, global_presence='values-only', section_presence=None):
        """Create a PublishConfig with a REQ table section."""
        data = {
            'attribute-presence': global_presence,
            'render': {
                'REQ': [
                    {
                        'type': 'table',
                        'attributes': [
                            {'id': {'alias': 'Identifier'}},
                            {'parent': {'alias': 'Parent'}},
                            {'status': {'alias': 'Status'}},
                            {'priority': {'alias': 'Priority'}},
                        ],
                    },
                ],
            },
        }
        if section_presence is not None:
            data['render']['REQ'][0]['attribute-presence'] = section_presence
        return PublishConfig.model_validate(data)

    def _make_context_with_metamodel(self, metamodel):
        """Create a mock RenderContext with a config that has a metamodel."""
        context = MagicMock()
        context.config.metamodel = metamodel
        return context

    def test_values_only_mode_skips_empty(self, simple_metamodel):
        """values-only: only attributes with values are rendered."""
        pub_config = self._make_pub_config(global_presence='values-only')
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'status': 'active'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')
        context = self._make_context_with_metamodel(simple_metamodel)

        result = render_block(block, pub_config, context)
        assert '| Identifier | REQ-1 |' in result
        assert '| Status | active |' in result
        assert '| Parent |' not in result
        assert '| Priority |' not in result

    def test_all_mode_renders_empty_cells(self, simple_metamodel):
        """all: all listed attributes rendered, empty cells for missing."""
        pub_config = self._make_pub_config(global_presence='all')
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'status': 'active'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')
        context = self._make_context_with_metamodel(simple_metamodel)

        result = render_block(block, pub_config, context)
        assert '| Identifier | REQ-1 |' in result
        assert '| Status | active |' in result
        assert '| Parent |  |' in result
        assert '| Priority |  |' in result

    def test_mandatory_mode_renders_mandatory_only(self, simple_metamodel):
        """mandatory: mandatory attributes rendered even without value; optional skipped."""
        pub_config = self._make_pub_config(global_presence='mandatory')
        # derive absent -> parent is mandatory
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'status': 'active'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')
        context = self._make_context_with_metamodel(simple_metamodel)

        result = render_block(block, pub_config, context)
        assert '| Identifier | REQ-1 |' in result
        assert '| Status | active |' in result
        assert '| Parent |  |' in result  # mandatory (condition holds)
        assert '| Priority |' not in result  # optional

    def test_mandatory_mode_conditional_not_active(self, simple_metamodel):
        """mandatory: conditional mandatory does NOT render when condition doesn't hold."""
        pub_config = self._make_pub_config(global_presence='mandatory')
        # derive='yes' -> parent is NOT mandatory
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'status': 'active', 'derive': 'yes'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')
        context = self._make_context_with_metamodel(simple_metamodel)

        result = render_block(block, pub_config, context)
        assert '| Parent |' not in result

    def test_section_override_takes_precedence(self, simple_metamodel):
        """Per-section attribute-presence overrides global."""
        pub_config = self._make_pub_config(global_presence='values-only', section_presence='all')
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'status': 'active'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')
        context = self._make_context_with_metamodel(simple_metamodel)

        result = render_block(block, pub_config, context)
        # Section says 'all', so empty cells should appear
        assert '| Parent |  |' in result
        assert '| Priority |  |' in result

    def test_mandatory_degrades_without_metamodel(self, caplog):
        """mandatory degrades to values-only when metamodel is unavailable, with warning."""
        pub_config = self._make_pub_config(global_presence='mandatory')
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'status': 'active'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')

        # Context with no metamodel
        context = MagicMock()
        context.config.metamodel = None

        with caplog.at_level(logging.WARNING):
            result = render_block(block, pub_config, context)

        # Should behave as values-only
        assert '| Identifier | REQ-1 |' in result
        assert '| Status | active |' in result
        assert '| Parent |' not in result
        # Should have logged a warning
        assert "degrading to 'values-only'" in caplog.text

    def test_no_context_defaults_to_values_only(self):
        """No context at all -> metamodel unavailable -> values-only behavior."""
        pub_config = self._make_pub_config(global_presence='all')
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'status': 'active'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')

        # When mode is 'all', metamodel is not needed for determination
        result = render_block(block, pub_config, context=None)
        assert '| Parent |  |' in result
        assert '| Priority |  |' in result


class TestTextSectionUnchanged:
    """Verify text sections always skip attributes without values."""

    def _make_text_pub_config(self, global_presence='all'):
        data = {
            'attribute-presence': global_presence,
            'render': {
                'REQ': [
                    {
                        'type': 'text',
                        'mode': 'block',
                        'attributes': [
                            {'contents': {'alias': 'Requirement'}},
                            {'priority': {'alias': 'Priority'}},
                        ],
                    },
                ],
            },
        }
        return PublishConfig.model_validate(data)

    def test_text_section_skips_empty_even_with_all_mode(self):
        """Text section always skips empty values regardless of global mode."""
        pub_config = self._make_text_pub_config(global_presence='all')
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'contents': 'System shall do X.'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')

        result = render_block(block, pub_config)
        assert '**Requirement**' in result
        assert 'System shall do X.' in result
        assert '**Priority**' not in result

    def test_text_section_renders_present_values(self):
        """Text section renders attributes that have values normally."""
        pub_config = self._make_text_pub_config(global_presence='values-only')
        artifact = _make_artifact('REQ-1', {'id': 'REQ-1', 'contents': 'Do X.', 'priority': '1'})
        block = ArtifactBlock(artifact=artifact, raw_text='raw')

        result = render_block(block, pub_config)
        assert '**Requirement**' in result
        assert 'Do X.' in result
        assert '**Priority**' in result
        assert '1' in result
