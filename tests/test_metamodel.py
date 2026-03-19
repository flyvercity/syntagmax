from pathlib import Path
from syntagmax.metamodel import load_model
import pytest

def test_load_model_with_comments(tmp_path):
    model_content = """# Comment at the start of file
artifact MyArtifact: # comment after artifact name
    # This is a comment line
    attribute myAttr is mandatory string # comment at end of line

    # another comment after blank line
    attribute myOtherAttr is optional integer
    
# Comment between artifacts
artifact AnotherArtifact:
    attribute name is mandatory string
"""
    model_file = tmp_path / "test_model.smx"
    model_file.write_text(model_content)
    
    model = load_model(model_file)
    
    artifacts = model['artifacts']
    assert "MyArtifact" in artifacts
    assert len(artifacts["MyArtifact"]["attributes"]) == 2
    assert artifacts["MyArtifact"]["attributes"][0]["name"] == "myAttr"
    assert artifacts["MyArtifact"]["attributes"][1]["name"] == "myOtherAttr"
    
    assert "AnotherArtifact" in artifacts
    assert len(artifacts["AnotherArtifact"]["attributes"]) == 1
    assert artifacts["AnotherArtifact"]["attributes"][0]["name"] == "name"

def test_load_model_empty_artifact(tmp_path):
    model_content = """artifact Empty:
    # only comments here
"""
    model_file = tmp_path / "empty_model.smx"
    model_file.write_text(model_content)
    
    model = load_model(model_file)
    artifacts = model['artifacts']
    assert "Empty" in artifacts
    assert len(artifacts["Empty"]["attributes"]) == 0
