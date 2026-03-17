# SPDX-License-Identifier: MIT
import pytest
from pathlib import Path
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.text import TextExtractor
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.artifact import Artifact
from syntagmax.params import Params

@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False)

@pytest.fixture
def config_file(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("""
base = "."
[[input]]
name = "test"
dir = "."
driver = "text"
atype = "requirement"
""", encoding='utf-8')
    return cfg_path

@pytest.fixture
def config(params, config_file):
    return Config(params=params, config_filename=config_file)

@pytest.fixture
def input_record(tmp_path):
    return InputRecord(
        name="test",
        record_base=tmp_path,
        filepaths=[],
        driver="text",
        default_atype="requirement"
    )

def test_text_extractor_basic(config, input_record, tmp_path):
    content = """
    Some text before.
    [<
    ID = REQ-1
    PID = userstory:US-1@1
    >>>
    This is the body of the requirement.
    >]
    Some text after.
    """
    filepath = tmp_path / "test.txt"
    filepath.write_text(content, encoding='utf-8')
    
    # We need to make sure the config's base_dir matches tmp_path or similar
    # In our fixture, config_file is in tmp_path, so root_dir is tmp_path.
    # config.base is ".", so base_dir is tmp_path.
    
    extractor = TextExtractor(config, input_record)
    artifacts, errors = extractor.extract_from_file(filepath)
    
    assert len(errors) == 0
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.aid == "REQ-1"
    assert artifact.atype == "requirement"
    assert len(artifact.pids) == 1
    assert artifact.pids[0].aid == "US-1"
    assert artifact.pids[0].atype == "userstory"

def test_obsidian_extractor_basic(config, input_record, tmp_path):
    content = """
    [REQ]
    This is the content.
    [id] REQ-2
    [atype] custom-type
    [pid] user-story:US-2
    ```yaml
    attrs:
      priority: high
    ```
    """
    filepath = tmp_path / "test.md"
    filepath.write_text(content, encoding='utf-8')
    
    extractor = ObsidianExtractor(config, input_record)
    artifacts, errors = extractor.extract_from_file(filepath)
    
    assert len(errors) == 0
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.aid == "REQ-2"
    assert artifact.atype == "custom-type"
    assert artifact.fields['priority'] == "high"
    assert "This is the content." in artifact.fields['content']

