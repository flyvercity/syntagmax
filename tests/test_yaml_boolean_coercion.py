# SPDX-License-Identifier: MIT
# Tests for YAML boolean coercion (GitHub issue #109).
# YAML 1.1 parses yes/no/on/off/true/false as Python booleans.
# The extractors must map them back to the appropriate metamodel labels.

import textwrap

import pytest

from syntagmax.analyse import ArtifactValidator
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.extractors.sidecar import SidecarExtractor
from syntagmax.extractors.simple_markdown import SimpleMarkdownExtractor
from syntagmax.params import Params


# -- Fixtures --


@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False)


@pytest.fixture
def config(params, tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        """
base = "."
[[input]]
name = "test"
dir = "."
driver = "obsidian"
atype = "REQ"
""",
        encoding='utf-8',
    )
    return Config(params=params, config_filename=cfg_path)


@pytest.fixture
def metamodel_custom_boolean():
    """Metamodel with custom boolean labels: true='yes', false='no'."""
    return {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}}],
                    'safety': [
                        {
                            'name': 'safety',
                            'presence': 'mandatory',
                            'multiple': False,
                            'type_info': {
                                'type': 'boolean',
                                'custom_values': {'true': ['yes'], 'false': ['no']},
                            },
                        }
                    ],
                    'derive': [
                        {
                            'name': 'derive',
                            'presence': 'mandatory',
                            'multiple': False,
                            'type_info': {
                                'type': 'boolean',
                                'custom_values': {'true': ['yes'], 'false': ['no']},
                            },
                        }
                    ],
                },
            }
        },
        'traces': {},
    }


@pytest.fixture
def metamodel_default_boolean():
    """Metamodel with default boolean (no custom labels)."""
    return {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}}],
                    'active': [
                        {
                            'name': 'active',
                            'presence': 'mandatory',
                            'multiple': False,
                            'type_info': {'type': 'boolean'},
                        }
                    ],
                },
            }
        },
        'traces': {},
    }


@pytest.fixture
def input_record(tmp_path):
    return InputRecord(name='test', dir='.', record_base=tmp_path, filepaths=[], driver='obsidian', default_atype='REQ', marker='REQ')


# -- Tests: _yaml_value_to_str helper --


class TestYamlValueToStr:
    """Tests for the Extractor._yaml_value_to_str helper method."""

    def test_non_bool_passthrough(self, config, input_record, metamodel_custom_boolean):
        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        assert extractor._yaml_value_to_str('hello', 'REQ', 'safety') == 'hello'
        assert extractor._yaml_value_to_str(42, 'REQ', 'safety') == '42'
        assert extractor._yaml_value_to_str(3.14, 'REQ', 'safety') == '3.14'

    def test_bool_with_custom_labels(self, config, input_record, metamodel_custom_boolean):
        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        assert extractor._yaml_value_to_str(False, 'REQ', 'safety') == 'no'
        assert extractor._yaml_value_to_str(True, 'REQ', 'safety') == 'yes'

    def test_bool_without_metamodel(self, config, input_record):
        extractor = ObsidianExtractor(config, input_record, metamodel=None)
        assert extractor._yaml_value_to_str(False, 'REQ', 'safety') == 'no'
        assert extractor._yaml_value_to_str(True, 'REQ', 'safety') == 'yes'

    def test_bool_default_boolean_type(self, config, input_record, metamodel_default_boolean):
        extractor = ObsidianExtractor(config, input_record, metamodel_default_boolean)
        # Default boolean has no custom_values, so falls back to yes/no
        assert extractor._yaml_value_to_str(False, 'REQ', 'active') == 'no'
        assert extractor._yaml_value_to_str(True, 'REQ', 'active') == 'yes'

    def test_bool_unknown_attribute(self, config, input_record, metamodel_custom_boolean):
        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        # Attribute not in metamodel — defaults to yes/no
        assert extractor._yaml_value_to_str(False, 'REQ', 'unknown_attr') == 'no'
        assert extractor._yaml_value_to_str(True, 'REQ', 'unknown_attr') == 'yes'

    def test_bool_unknown_atype(self, config, input_record, metamodel_custom_boolean):
        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        assert extractor._yaml_value_to_str(False, 'UNKNOWN', 'safety') == 'no'
        assert extractor._yaml_value_to_str(True, 'UNKNOWN', 'safety') == 'yes'


# -- Tests: Obsidian (Markdown) extractor end-to-end --


class TestObsidianExtractorBooleanCoercion:
    """End-to-end tests for issue #109: YAML boolean coercion in Obsidian extractor."""

    def test_yaml_no_value_extracted_as_no(self, config, input_record, metamodel_custom_boolean, tmp_path):
        """The exact scenario from issue #109: safety: no should extract as 'no'."""
        contents = textwrap.dedent("""\
            [REQ]
            Requirement body.
            [id] SCHED-SRS-001
            ```yaml
            attrs:
              safety: no
              derive: no
            ```
        """)
        filepath = tmp_path / 'test.md'
        filepath.write_text(contents, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        artifacts, errors = extractor.extract_from_file(filepath)

        assert len(errors) == 0
        assert len(artifacts) == 1
        assert artifacts[0].fields['safety'] == 'no'
        assert artifacts[0].fields['derive'] == 'no'

    def test_yaml_yes_value_extracted_as_yes(self, config, input_record, metamodel_custom_boolean, tmp_path):
        contents = textwrap.dedent("""\
            [REQ]
            Requirement body.
            [id] SCHED-SRS-002
            ```yaml
            attrs:
              safety: yes
              derive: yes
            ```
        """)
        filepath = tmp_path / 'test.md'
        filepath.write_text(contents, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        artifacts, errors = extractor.extract_from_file(filepath)

        assert len(errors) == 0
        assert len(artifacts) == 1
        assert artifacts[0].fields['safety'] == 'yes'
        assert artifacts[0].fields['derive'] == 'yes'

    def test_yaml_boolean_passes_validation(self, config, input_record, metamodel_custom_boolean, tmp_path):
        """Full pipeline: extraction + validation should produce no errors."""
        contents = textwrap.dedent("""\
            [REQ]
            Requirement body.
            [id] REQ-001
            ```yaml
            attrs:
              safety: no
              derive: yes
            ```
        """)
        filepath = tmp_path / 'test.md'
        filepath.write_text(contents, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        artifacts, errors = extractor.extract_from_file(filepath)

        assert len(errors) == 0
        assert len(artifacts) == 1

        artifact = artifacts[0]
        validator = ArtifactValidator(metamodel_custom_boolean, {artifact.aid: artifact})
        val_errors = validator.validate(artifact)
        assert not val_errors, f'Unexpected validation errors: {val_errors}'

    def test_yaml_on_off_with_default_boolean(self, config, input_record, metamodel_default_boolean, tmp_path):
        """YAML on/off values should also be coerced correctly."""
        contents = textwrap.dedent("""\
            [REQ]
            Body.
            [id] REQ-003
            ```yaml
            attrs:
              active: on
            ```
        """)
        filepath = tmp_path / 'test.md'
        filepath.write_text(contents, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record, metamodel_default_boolean)
        artifacts, errors = extractor.extract_from_file(filepath)

        assert len(errors) == 0
        assert len(artifacts) == 1
        # 'on' is parsed as True by YAML, then converted to 'yes' (default label)
        assert artifacts[0].fields['active'] == 'yes'

    def test_yaml_true_false_with_default_boolean(self, config, input_record, metamodel_default_boolean, tmp_path):
        """YAML true/false literals should be coerced to yes/no."""
        contents = textwrap.dedent("""\
            [REQ]
            Body.
            [id] REQ-004
            ```yaml
            attrs:
              active: true
            ```
        """)
        filepath = tmp_path / 'test.md'
        filepath.write_text(contents, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record, metamodel_default_boolean)
        artifacts, errors = extractor.extract_from_file(filepath)

        assert len(errors) == 0
        assert len(artifacts) == 1
        assert artifacts[0].fields['active'] == 'yes'

    def test_quoted_no_preserved_as_string(self, config, input_record, metamodel_custom_boolean, tmp_path):
        """Quoted 'no' in YAML is a string, not a boolean — should pass through unchanged."""
        contents = textwrap.dedent("""\
            [REQ]
            Body.
            [id] REQ-005
            ```yaml
            attrs:
              safety: "no"
              derive: "yes"
            ```
        """)
        filepath = tmp_path / 'test.md'
        filepath.write_text(contents, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record, metamodel_custom_boolean)
        artifacts, errors = extractor.extract_from_file(filepath)

        assert len(errors) == 0
        assert len(artifacts) == 1
        assert artifacts[0].fields['safety'] == 'no'
        assert artifacts[0].fields['derive'] == 'yes'


# -- Tests: Sidecar extractor --


class TestSidecarExtractorBooleanCoercion:
    """Tests for YAML boolean coercion in the sidecar extractor."""

    def test_sidecar_no_value_coerced(self, config, tmp_path, metamodel_custom_boolean):
        # Create an image file and its sidecar
        img_path = tmp_path / 'diagram.png'
        img_path.write_bytes(b'\x89PNG')

        sidecar = tmp_path / 'diagram.png.stmx'
        sidecar.write_text(
            textwrap.dedent("""\
                id: REQ-SC-001
                safety: no
                derive: yes
                contents: A diagram
            """),
            encoding='utf-8',
        )

        record = InputRecord(
            name='test', dir='.', record_base=tmp_path,
            filepaths=[img_path], driver='sidecar', default_atype='REQ', marker='REQ',
        )

        extractor = SidecarExtractor(config, record, metamodel_custom_boolean)
        artifacts, errors = extractor.extract_from_file(img_path)

        assert len(errors) == 0
        assert len(artifacts) == 1
        assert artifacts[0].fields['safety'] == 'no'
        assert artifacts[0].fields['derive'] == 'yes'


# -- Tests: Simple Markdown extractor --


class TestSimpleMarkdownExtractorBooleanCoercion:
    """Tests for YAML boolean coercion in the simple-markdown extractor."""

    def test_frontmatter_no_value_coerced(self, config, tmp_path, metamodel_custom_boolean):
        md_path = tmp_path / 'requirement.md'
        md_path.write_text(
            textwrap.dedent("""\
                ---
                id: REQ-SM-001
                safety: no
                derive: yes
                ---
                Requirement body text.
            """),
            encoding='utf-8',
        )

        record = InputRecord(
            name='test', dir='.', record_base=tmp_path,
            filepaths=[md_path], driver='simple-markdown', default_atype='REQ', marker='REQ',
        )

        extractor = SimpleMarkdownExtractor(config, record, metamodel_custom_boolean)
        artifacts, errors = extractor.extract_from_file(md_path)

        assert len(errors) == 0
        assert len(artifacts) == 1
        assert artifacts[0].fields['safety'] == 'no'
        assert artifacts[0].fields['derive'] == 'yes'
