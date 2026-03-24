import pytest
from syntagmax.metamodel import load_metamodel
from syntagmax.analyse import ArtifactValidator
from syntagmax.artifact import Artifact


@pytest.fixture
def metamodel(tmp_path):
    model_content = """
artifact REQ:
    id is string
    attribute contents is mandatory string
    attribute tags is optional multiple string
    attribute count is optional integer
    attribute flags is optional multiple boolean
    attribute status is optional enum [Draft, Final]
"""
    model_file = tmp_path / 'test.model'
    model_file.write_text(model_content)
    errors = []
    return load_metamodel(model_file, errors, validate=True)


def test_multiple_attribute_valid(metamodel):
    validator = ArtifactValidator(metamodel, {})
    art = Artifact(None)
    art.atype = 'REQ'
    art.aid = '1'
    art.fields = {'id': '1', 'contents': 'some content', 'tags': ['tag1', 'tag2'], 'flags': ['true', 'false', 'yes']}
    errors = validator.validate(art)
    assert not errors


def test_multiple_attribute_invalid_not_list(metamodel):
    validator = ArtifactValidator(metamodel, {})
    art = Artifact(None)
    art.atype = 'REQ'
    art.aid = '1'
    art.fields = {'id': '1', 'contents': 'some content', 'tags': 'not-a-list'}
    errors = validator.validate(art)
    assert any('must be a list' in e for e in errors)


def test_single_attribute_invalid_is_list(metamodel):
    validator = ArtifactValidator(metamodel, {})
    art = Artifact(None)
    art.atype = 'REQ'
    art.aid = '1'
    art.fields = {'id': '1', 'contents': 'some content', 'count': ['1', '2']}
    errors = validator.validate(art)
    assert any('must not be a list' in e for e in errors)


def test_multiple_attribute_type_check(metamodel):
    validator = ArtifactValidator(metamodel, {})
    art = Artifact(None)
    art.atype = 'REQ'
    art.aid = '1'
    art.fields = {'id': '1', 'contents': 'some content', 'flags': ['true', 'invalid-bool']}
    errors = validator.validate(art)
    assert any('not a valid boolean' in e for e in errors)


def test_mandatory_missing(metamodel):
    validator = ArtifactValidator(metamodel, {})
    art = Artifact(None)
    art.atype = 'REQ'
    art.aid = '1'
    art.fields = {'tags': ['t1']}
    errors = validator.validate(art)
    assert any("Missing mandatory attribute: 'id'" in e for e in errors)
    assert any("Missing mandatory attribute: 'contents'" in e for e in errors)


def test_enum_validation(metamodel):
    validator = ArtifactValidator(metamodel, {})
    art = Artifact(None)
    art.atype = 'REQ'
    art.aid = '1'
    art.fields = {'id': '1', 'contents': 'some content', 'status': 'Draft'}
    errors = validator.validate(art)
    assert not errors

    art.fields['status'] = 'Invalid'
    errors = validator.validate(art)
    assert any('is invalid. Allowed values' in e for e in errors)


def test_mandatory_multiple_missing(tmp_path):
    model_content = """
artifact REQ:
    id is string
    attribute contents is mandatory string
    attribute tags is mandatory multiple string
"""
    model_file = tmp_path / 'test2.model'
    model_file.write_text(model_content)
    errors = []
    metamodel = load_metamodel(model_file, errors, validate=True)
    validator = ArtifactValidator(metamodel, {})

    art = Artifact(None)
    art.atype = 'REQ'
    art.aid = '1'
    art.fields = {'id': '1', 'contents': 'some content'}
    errors = validator.validate(art)
    assert any("Missing mandatory attribute: 'tags'" in e for e in errors)
