import pytest
from syntagmax.metamodel import load_metamodel
from syntagmax.analyse import ArtifactValidator
from syntagmax.artifact import Artifact

@pytest.fixture
def validator(tmp_path):
    model_content = """
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute link is optional reference

artifact SRS:
    attribute id is mandatory string
    attribute contents is mandatory string
"""
    model_file = tmp_path / "test.model"
    model_file.write_text(model_content)

    errors = []
    metamodel = load_metamodel(model_file, errors, validate=True)

    ref_art1 = Artifact(None)
    ref_art1.atype = 'SRS'
    ref_art1.aid = '001'

    ref_art2 = Artifact(None)
    ref_art2.atype = 'XYZ'
    ref_art2.aid = '002'

    artifacts = {'001': ref_art1, '002': ref_art2}
    return ArtifactValidator(metamodel, artifacts)


def test_valid_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "001"}
    errors = validator.validate(art)
    assert not errors

def test_malformed_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "INVALID_REF"}
    errors = validator.validate(art)
    assert any("unknown artifact id" in e.lower() for e in errors)

def test_unknown_type_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "002"}
    errors = validator.validate(art)
    assert any("artifact with unknown type" in e.lower() for e in errors)

