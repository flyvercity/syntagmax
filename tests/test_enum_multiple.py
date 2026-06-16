import pytest
import textwrap
from pathlib import Path
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.text import TextExtractor
from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.analyse import ArtifactValidator
from syntagmax.params import Params
from syntagmax.metamodel import load_metamodel

@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False)

@pytest.fixture
def metamodel_file(tmp_path):
    content = textwrap.dedent("""
        artifact REQ:
            id is string
            attribute contents is mandatory string
            attribute allocation is optional enum multiple [HW, SW, FW]
            attribute mytags is optional multiple enum [tagone, tagtwo]
    """)
    f = tmp_path / "test.smx"
    f.write_text(content)
    return f

@pytest.fixture
def metamodel(metamodel_file):
    errors = []
    return load_metamodel(metamodel_file, errors, validate=True)

@pytest.fixture
def config(params, tmp_path, metamodel_file):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(f"""
base = "."
[metamodel]
filename = "{metamodel_file.name}"
[[input]]
name = "test"
dir = "."
driver = "text"
atype = "REQ"
""", encoding='utf-8')
    return Config(params=params, config_filename=cfg_path)

def test_text_extractor_enum_multiple(config, metamodel, tmp_path):
    contents = """
    [<
    ID = REQ-1
    allocation = HW
    allocation = SW
    mytags = tagone
    >>>
    Test 1
    >]
    [<
    ID = REQ-2
    allocation = FW, HW
    mytags = tagone, tagtwo
    >>>
    Test 2
    >]
    """
    filepath = tmp_path / 'test.txt'
    filepath.write_text(contents, encoding='utf-8')

    input_record = config.input_records()[0]
    extractor = TextExtractor(config, input_record, metamodel=metamodel)
    artifacts, errors = extractor.extract_from_file(filepath)

    assert not errors
    assert len(artifacts) == 2

    assert artifacts[0].aid == 'REQ-1'
    assert artifacts[0].fields['allocation'] == ['HW', 'SW']
    assert artifacts[0].fields['mytags'] == ['tagone']

    assert artifacts[1].aid == 'REQ-2'
    assert artifacts[1].fields['allocation'] == ['FW', 'HW']
    assert artifacts[1].fields['mytags'] == ['tagone', 'tagtwo']

def test_markdown_extractor_enum_multiple(config, metamodel, tmp_path):
    contents = textwrap.dedent("""
    [REQ]
    Test 3
    [id] REQ-3
    [allocation] HW, FW
    [mytags] tagone
    [mytags] tagtwo
    [/REQ]
    """).strip()
    filepath = tmp_path / 'test.md'
    filepath.write_text(contents, encoding='utf-8')

    input_record = InputRecord(name='test_md', record_base=tmp_path, filepaths=[], driver='markdown', default_atype='REQ', marker='REQ')
    extractor = MarkdownExtractor(config, input_record, metamodel=metamodel)
    artifacts, errors = extractor.extract_from_file(filepath)

    assert not errors
    assert len(artifacts) == 1
    assert artifacts[0].aid == 'REQ-3'
    assert artifacts[0].fields['allocation'] == ['HW', 'FW']
    assert artifacts[0].fields['mytags'] == ['tagone', 'tagtwo']

def test_enum_multiple_validation(metamodel):
    from syntagmax.artifact import Artifact
    class MockConfig:
        def base_dir(self): return Path(".")

    config = MockConfig()
    validator = ArtifactValidator(metamodel, {})

    # Valid
    a1 = Artifact(config)
    a1.atype = 'REQ'
    a1.aid = 'REQ-1'
    a1.fields = {'id': 'REQ-1', 'contents': 'test', 'allocation': ['HW', 'SW']}
    assert not validator.validate(a1)

    # Invalid value
    a2 = Artifact(config)
    a2.atype = 'REQ'
    a2.aid = 'REQ-2'
    a2.fields = {'id': 'REQ-2', 'contents': 'test', 'allocation': ['HW', 'INVALID']}
    errors = validator.validate(a2)
    assert any("is invalid. Allowed values" in e for e in errors)

    # Not a list
    a3 = Artifact(config)
    a3.atype = 'REQ'
    a3.aid = 'REQ-3'
    a3.fields = {'id': 'REQ-3', 'contents': 'test', 'allocation': 'HW'}
    errors = validator.validate(a3)
    assert any("must be a list" in e for e in errors)
