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
    
    assert "MyArtifact" in model
    assert len(model["MyArtifact"]["attributes"]) == 2
    assert model["MyArtifact"]["attributes"][0]["name"] == "myAttr"
    assert model["MyArtifact"]["attributes"][1]["name"] == "myOtherAttr"
    
    assert "AnotherArtifact" in model
    assert len(model["AnotherArtifact"]["attributes"]) == 1
    assert model["AnotherArtifact"]["attributes"][0]["name"] == "name"

def test_load_model_empty_artifact(tmp_path):
    model_content = """artifact Empty:
    # only comments here
"""
    model_file = tmp_path / "empty_model.smx"
    model_file.write_text(model_content)
    
    model = load_model(model_file)
    assert "Empty" in model
    assert len(model["Empty"]["attributes"]) == 0
