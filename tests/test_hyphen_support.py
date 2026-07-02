import textwrap
from syntagmax.metamodel import load_metamodel
from syntagmax.params import Params
from syntagmax.config import Config


def test_hyphenated_and_underscored_names(tmp_path):
    model_content = textwrap.dedent("""
        artifact system-req:
            id is string as {atype}-{num:3}
            attribute contents is mandatory string
            attribute doors-id is optional string
            attribute secret_flag is optional boolean
            attribute status-value is optional enum [draft, in-review, approved_final]

        artifact sub_component:
            id is string
            attribute contents is mandatory string
            attribute parent-link is mandatory reference to parent if secret_flag

        trace from system-req to sub_component is optional via commit if secret_flag
        """)
    model_file = tmp_path / 'hyphen.smx'
    model_file.write_text(model_content)

    errors = []
    # Note: secret_flag is defined in system-req but used in sub_component.
    # The anchor must exist in the artifact where it is used.
    # Actually, in the trace rule, it's checked in the source_atype.
    # But in sub_component's parent-link rule, it's checked in sub_component.
    # Let me fix the test metamodel.
    model_content_fixed = textwrap.dedent("""
        artifact system-req:
            id is string as {atype}-{num:3}
            attribute contents is mandatory string
            attribute doors-id is optional string
            attribute secret_flag is optional boolean
            attribute status-value is optional enum [draft, in-review, approved_final]

        artifact sub_component:
            id is string
            attribute contents is mandatory string
            attribute secret_flag is optional boolean
            attribute parent-link is mandatory reference to parent if secret_flag

        trace from system-req to sub_component is optional via commit if secret_flag
        """)
    model_file.write_text(model_content_fixed)

    model = load_metamodel(model_file, errors, validate=True)

    assert not errors
    assert 'system-req' in model['artifacts']
    assert 'sub_component' in model['artifacts']

    sys_req_attrs = model['artifacts']['system-req']['attributes']
    assert 'doors-id' in sys_req_attrs
    assert 'secret_flag' in sys_req_attrs
    assert 'status-value' in sys_req_attrs

    assert sys_req_attrs['status-value'][0]['type_info']['allowed'] == ['draft', 'in-review', 'approved_final']

    assert 'system-req' in model['traces']
    trace = model['traces']['system-req'][0]
    assert trace['source'] == 'system-req'
    assert trace['targets'] == ['sub_component']
    assert trace['condition']['anchor'] == 'secret_flag'


def test_text_extractor_with_hyphens(tmp_path):
    from syntagmax.extractors.text import TextExtractor

    model_content = textwrap.dedent("""
        artifact system-req:
            id is string
            attribute contents is mandatory string
            attribute doors-id is optional string
        """)
    model_file = tmp_path / 'model.smx'
    model_file.write_text(model_content)

    config_content = textwrap.dedent("""
        base = "."
        [[input]]
        name = "test"
        dir = "."
        driver = "text"
        atype = "system-req"

        [metamodel]
        filename = "model.smx"
    """)
    config_file = tmp_path / 'config.toml'
    config_file.write_text(config_content)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_file)
    record = config.input_records()[0]

    extractor = TextExtractor(config, record, config.metamodel)

    code_content = textwrap.dedent("""
        // [< id=SR-001 doors-id=D-101 >>>
        // Requirement contents
        // >]
    """)
    code_file = tmp_path / 'test.cpp'
    code_file.write_text(code_content)

    artifacts, errors = extractor.extract_from_file(code_file)

    assert not errors
    assert len(artifacts) == 1
    assert artifacts[0].aid == 'SR-001'
    assert artifacts[0].fields['doors-id'] == 'D-101'


def test_markdown_extractor_with_hyphens(tmp_path):
    from syntagmax.extractors.markdown import MarkdownExtractor

    model_content = textwrap.dedent("""
        artifact system-req:
            id is string
            attribute contents is mandatory string
            attribute doors-id is optional string
        """)
    model_file = tmp_path / 'model.smx'
    model_file.write_text(model_content)

    config_content = textwrap.dedent("""
        base = "."
        [[input]]
        name = "test"
        dir = "."
        driver = "markdown"
        atype = "system-req"
        marker = "REQ"

        [metamodel]
        filename = "model.smx"
    """)
    config_file = tmp_path / 'config.toml'
    config_file.write_text(config_content)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_file)
    record = config.input_records()[0]

    extractor = MarkdownExtractor(config, record, config.metamodel)

    md_content = textwrap.dedent("""
        [REQ]
        Requirement contents
        [id] SR-001
        [doors-id] D-101
        [/REQ]
    """)
    md_file = tmp_path / 'test.md'
    md_file.write_text(md_content)

    from syntagmax.artifact import LineLocation

    def location_builder(start, end):
        return LineLocation(loc_file='test.md', loc_lines=(start, end))

    artifacts, errors = extractor._extract_from_markdown(md_file, md_content, location_builder)

    assert not errors
    assert len(artifacts) == 1
    assert artifacts[0].aid == 'SR-001'
    assert artifacts[0].fields['doors-id'] == 'D-101'
