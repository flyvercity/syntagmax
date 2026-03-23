
import pytest
from pathlib import Path
from syntagmax.metamodel import load_metamodel
from syntagmax.artifact import Artifact, ArtifactMap
from syntagmax.analyse import ArtifactValidator
from syntagmax.config import Config
from syntagmax.errors import FatalError

@pytest.fixture
def mock_config():
    class MockConfig:
        def __init__(self):
            self.params = {'verbose': False}
    return MockConfig()

def test_id_schema_validation(tmp_path):
    model_file = tmp_path / "project.syntagmax"
    model_file.write_text("""
artifact REQ:
    id is string as REQ-{num:3}
    attribute contents is mandatory string

artifact SYS:
    id is string as {atype}-{num}
    attribute contents is mandatory string
""")

    errors = []
    metamodel = load_metamodel(model_file, errors)
    assert not errors

    artifacts: ArtifactMap = {}

    # Valid REQ
    a1 = Artifact(None)
    a1.atype = 'REQ'
    a1.aid = 'REQ-001'
    a1.fields = {'contents': 'test', 'id': 'REQ-001'}
    artifacts[a1.aid] = a1

    # Invalid REQ (wrong padding)
    a2 = Artifact(None)
    a2.atype = 'REQ'
    a2.aid = 'REQ-1'
    a2.fields = {'contents': 'test', 'id': 'REQ-1'}
    artifacts[a2.aid] = a2

    # Valid SYS
    a3 = Artifact(None)
    a3.atype = 'SYS'
    a3.aid = 'SYS-123'
    a3.fields = {'contents': 'test', 'id': 'SYS-123'}
    artifacts[a3.aid] = a3

    # Invalid SYS (wrong type)
    a4 = Artifact(None)
    a4.atype = 'SYS'
    a4.aid = 'REQ-123'
    a4.fields = {'contents': 'test', 'id': 'REQ-123'}
    artifacts[a4.aid] = a4

    validator = ArtifactValidator(metamodel, artifacts)

    v_errors = validator.validate(a1)
    assert not v_errors, f"a1 should be valid, errors: {v_errors}"

    validator = ArtifactValidator(metamodel, artifacts)
    v_errors = validator.validate(a2)
    assert any("does not match schema" in e for e in v_errors), f"a2 should have schema error, errors: {v_errors}"

    validator = ArtifactValidator(metamodel, artifacts)
    v_errors = validator.validate(a3)
    assert not v_errors, f"a3 should be valid, errors: {v_errors}"

    validator = ArtifactValidator(metamodel, artifacts)
    v_errors = validator.validate(a4)
    assert any("does not match schema" in e for e in v_errors), f"a4 should have schema error, errors: {v_errors}"

def test_id_attribute_forbidden(tmp_path):
    model_file = tmp_path / "project.syntagmax"
    model_file.write_text("""
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
""")
    errors = []
    with pytest.raises(FatalError) as excinfo:
        load_metamodel(model_file, errors)
    assert any("regular attribute named 'id'" in e for e in excinfo.value.errors)

def test_id_schema_with_spaces(tmp_path):
    model_file = tmp_path / "project.syntagmax"
    model_file.write_text("""
artifact REQ:
    id is string as "Project REQ-{num:3}"
    attribute contents is mandatory string
""")
    errors = []
    metamodel = load_metamodel(model_file, errors)
    assert not errors
    assert metamodel['artifacts']['REQ']['attributes']['id']['schema'] == "Project REQ-{num:3}"
