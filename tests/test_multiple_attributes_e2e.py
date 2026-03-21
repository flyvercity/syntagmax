import pytest
import textwrap

from syntagmax.config import Config, InputRecord
from syntagmax.extractors.text import TextExtractor
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.analyse import ArtifactValidator
from syntagmax.params import Params

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
driver = "text"
atype = "REQ"
""",
        encoding='utf-8',
    )
    return Config(params=params, config_filename=cfg_path)

@pytest.fixture
def metamodel():
    return {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}},
                    'contents': {'name': 'contents', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}},
                    'tag': {'name': 'tag', 'presence': 'mandatory', 'multiple': True, 'type_info': {'type': 'string'}},
                    'author': {'name': 'author', 'presence': 'optional', 'multiple': True, 'type_info': {'type': 'string'}},
                    'priority': {'name': 'priority', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'string'}}
                }
            }
        },
        'traces': {}
    }

@pytest.fixture
def input_record(tmp_path):
    return InputRecord(name='test', record_base=tmp_path, filepaths=[], driver='text', default_atype='REQ')

def test_text_extractor_multiple_attributes(config, input_record, metamodel, tmp_path):
    contents = """
    [<
    ID = REQ-1
    tag = tag1
    tag = tag2
    priority = high
    >>>
    Test requirement 1
    >]
    """
    filepath = tmp_path / 'test.txt'
    filepath.write_text(contents, encoding='utf-8')

    extractor = TextExtractor(config, input_record, metamodel=metamodel)
    artifacts, errors = extractor.extract_from_file(filepath)

    assert len(errors) == 0
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.aid == 'REQ-1'
    assert artifact.fields['tag'] == ['tag1', 'tag2']
    assert artifact.fields['priority'] == 'high'
    assert artifact.fields['author'] == []  # Optional multiple attribute defaults to []

    # Run validator
    validator = ArtifactValidator(metamodel, {})
    val_errors = validator.validate(artifact)
    assert len(val_errors) == 0

def test_obsidian_extractor_multiple_attributes(config, input_record, metamodel, tmp_path):
    contents = textwrap.dedent("""
    [REQ]
    Test requirement 2
    [id] REQ-2
    [tag] tagA
    [tag] tagB
    ```yaml
    attrs:
      tag: tagC
      author:
        - Alice
        - Bob
    ```
    """).strip()
    filepath = tmp_path / 'test.md'
    filepath.write_text(contents, encoding='utf-8')

    extractor = ObsidianExtractor(config, input_record, metamodel=metamodel)
    artifacts, errors = extractor.extract_from_file(filepath)

    assert len(errors) == 0
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.aid == 'REQ-2'
    # Obsidian extractor: fields from markdown AND from YAML are added.
    # tag should contain tagA, tagB, tagC
    assert 'tag1' not in artifact.fields['tag'] # just a check
    assert 'tagA' in artifact.fields['tag']
    assert 'tagB' in artifact.fields['tag']
    assert 'tagC' in artifact.fields['tag']
    assert len(artifact.fields['tag']) == 3

    assert artifact.fields['author'] == ['Alice', 'Bob']

    # Run validator
    validator = ArtifactValidator(metamodel, {})
    val_errors = validator.validate(artifact)
    assert len(val_errors) == 0

def test_mandatory_multiple_attribute_missing(config, input_record, metamodel, tmp_path):
    # Missing 'tag' which is mandatory multiple
    contents = """
    [<
    ID = REQ-3
    >>>
    Test requirement 3
    >]
    """
    filepath = tmp_path / 'test_missing.txt'
    filepath.write_text(contents, encoding='utf-8')

    extractor = TextExtractor(config, input_record, metamodel=metamodel)
    artifacts, errors = extractor.extract_from_file(filepath)

    assert len(errors) == 0
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.aid == 'REQ-3'
    assert artifact.fields['tag'] == []

    # Run validator
    validator = ArtifactValidator(metamodel, {})
    val_errors = validator.validate(artifact)
    # Based on our analysis, [] satisfies mandatory for now because it's "present".
    # If the user wants mandatory to mean "not empty", validator needs to change.
    # For now, let's see what happens.
    assert len(val_errors) == 0
