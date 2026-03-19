import pytest
from pathlib import Path
from syntagmax.metamodel import load_metamodel
from syntagmax.analyse import ArtifactValidator
from syntagmax.artifact import Artifact, ARef
from syntagmax.config import Config

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
    return ArtifactValidator(metamodel)

def test_valid_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "SRS-001"}
    errors = validator.validate(art)
    assert not errors

def test_malformed_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "INVALID_REF"}
    errors = validator.validate(art)
    assert any("malformed reference" in e.lower() for e in errors)

def test_unknown_type_reference(validator):
    art = Artifact(None)
    art.atype = "REQ"
    art.aid = "1"
    art.fields = {"id": "1", "contents": "test", "link": "XYZ-001"}
    errors = validator.validate(art)
    assert any("unknown artifact type" in e.lower() for e in errors)
