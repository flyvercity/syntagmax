import pytest
from pathlib import Path
from syntagmax.metamodel import load_metamodel
from syntagmax.errors import FatalError

def test_invalid_placeholder_validation(tmp_path):
    model = tmp_path / "test.model"
    model.write_text("""
artifact REQ:
    id is string as REQ-{invalid}
    attribute contents is mandatory string
""", encoding='utf-8')
    
    errors = []
    with pytest.raises(FatalError) as excinfo:
        load_metamodel(model, errors)
    
    assert "Invalid placeholder: {invalid}" in str(excinfo.value)

def test_unbalanced_brace_validation(tmp_path):
    model = tmp_path / "test.model"
    model.write_text("""
artifact REQ:
    id is string as REQ-{num:4
    attribute contents is mandatory string
""", encoding='utf-8')
    
    errors = []
    # This will be caught by Lark itself because it won't match the new grammar
    with pytest.raises(FatalError):
        load_metamodel(model, errors)
