# SPDX-License-Identifier: MIT
import pytest
from pathlib import Path
from pydantic import ValidationError
from syntagmax.publish_config import PublishConfig, load_publish_config, resolve_publish_file, TableSection, TextSection, MarkerRenderSection
from syntagmax.errors import FatalError


def test_default_publish_config():
    config = PublishConfig()
    assert config.start_level == 1
    assert config.remove_numeric_prefixes_in_headers is True
    assert config.include_plain_text is True
    assert config.render == {}


def test_valid_publish_config_parsing():
    data = {
        'start_level': 2,
        'remove_numeric_prefixes_in_headers': False,
        'render': {
            'REQ': [
                {'type': 'table', 'attributes': [{'id': {'alias': 'ID'}}, {'parent': {'alias': 'Parent'}}]},
                {'type': 'text', 'mode': 'block', 'attributes': [{'contents': {'alias': 'Requirement'}}]},
            ],
            'COM': [{'type': 'text', 'mode': 'inline', 'alias': 'Comment'}],
        },
    }
    config = PublishConfig.model_validate(data)
    assert config.start_level == 2
    assert config.remove_numeric_prefixes_in_headers is False
    assert len(config.render['REQ']) == 2

    assert isinstance(config.render['REQ'][0], TableSection)
    assert config.render['REQ'][0].type == 'table'
    assert config.render['REQ'][0].attributes[0]['id'].alias == 'ID'

    assert isinstance(config.render['REQ'][1], TextSection)
    assert config.render['REQ'][1].type == 'text'
    assert config.render['REQ'][1].mode == 'block'

    assert isinstance(config.render['COM'][0], MarkerRenderSection)
    assert config.render['COM'][0].alias == 'Comment'
    assert config.render['COM'][0].mode == 'inline'


def test_invalid_attributes_multiple_keys():
    # Multiple keys in one attributes dict is invalid
    data = {'type': 'table', 'attributes': [{'id': {'alias': 'ID'}, 'parent': {'alias': 'Parent'}}]}
    with pytest.raises(ValidationError):
        TableSection.model_validate(data)


def test_invalid_extra_fields():
    # MarkerRenderSection cannot have attributes
    data = {'type': 'text', 'mode': 'block', 'alias': 'Comment', 'attributes': []}
    with pytest.raises(ValidationError):
        MarkerRenderSection.model_validate(data)

    # TextSection cannot have alias
    data2 = {'type': 'text', 'mode': 'block', 'attributes': [{'contents': {'alias': 'Requirement'}}], 'alias': 'Comment'}
    with pytest.raises(ValidationError):
        TextSection.model_validate(data2)


def test_load_publish_config_defaults(tmp_path):
    config = load_publish_config(None, tmp_path)
    assert config.start_level == 1

    config2 = load_publish_config(Path('nonexistent.yaml'), tmp_path)
    assert config2.start_level == 1


def test_load_publish_config_valid_file(tmp_path):
    yaml_content = """
start_level: 3
render:
  REQ:
    - type: text
      mode: inline
      attributes:
        - contents:
            alias: "ReqText"
"""
    p = tmp_path / 'publish.yaml'
    p.write_text(yaml_content, encoding='utf-8')
    config = load_publish_config(Path('publish.yaml'), tmp_path)
    assert config.start_level == 3
    assert 'REQ' in config.render


def test_load_publish_config_invalid_file(tmp_path):
    p = tmp_path / 'bad.yaml'
    p.write_text("start_level: 'not-an-int'", encoding='utf-8')
    with pytest.raises(FatalError):
        load_publish_config(Path('bad.yaml'), tmp_path)


def test_config_resolution(tmp_path):
    from syntagmax.config import Config
    from syntagmax.params import Params

    cfg_path = tmp_path / 'config.toml'
    cfg_content = """
base = "."
[[input]]
name = "r1"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
publish = "custom.yaml"

[[input]]
name = "r2"
dir = "SRS"
driver = "obsidian"
atype = "SRS"
"""
    cfg_path.write_text(cfg_content, encoding='utf-8')

    # Create record-specific custom.yaml
    custom_yaml = tmp_path / 'custom.yaml'
    custom_yaml.write_text('start_level: 5', encoding='utf-8')

    # Create default .syntagmax/publish.yaml
    dot_syntagmax = tmp_path / '.syntagmax'
    dot_syntagmax.mkdir()
    default_yaml = dot_syntagmax / 'publish.yaml'
    default_yaml.write_text('start_level: 2', encoding='utf-8')

    params = Params(verbose=False, render_tree=False, ai=False, output='console')
    config = Config(params=params, config_filename=cfg_path)
    records = config.input_records()

    assert len(records) == 2
    assert records[0].publish_config == 'custom.yaml'
    assert records[1].publish_config is None

    # Resolve for r1 (should be custom.yaml -> start_level=5)
    config_r1 = config.load_publish_config(records[0])
    assert config_r1.start_level == 5

    # Resolve for r2 (should fall back to .syntagmax/publish.yaml -> start_level=2)
    config_r2 = config.load_publish_config(records[1])
    assert config_r2.start_level == 2



class TestDocxTemplate:
    def test_docx_template_absent(self):
        config = PublishConfig()
        assert config.docx_template is None

    def test_docx_template_with_default_template(self):
        data = {
            'docx-template': {
                'default-template': 'templates/corp.dotm',
            },
        }
        config = PublishConfig.model_validate(data)
        assert config.docx_template is not None
        assert config.docx_template.default_template == 'templates/corp.dotm'
        assert config.docx_template.overrides == {}

    def test_docx_template_with_overrides(self):
        data = {
            'docx-template': {
                'default-template': 'templates/default.dotm',
                'overrides': {
                    'system-requirements': 'templates/sys.dotm',
                    'implementation': 'none',
                },
            },
        }
        config = PublishConfig.model_validate(data)
        assert config.docx_template.default_template == 'templates/default.dotm'
        assert config.docx_template.overrides['system-requirements'] == 'templates/sys.dotm'
        assert config.docx_template.overrides['implementation'] == 'none'

    def test_docx_template_none_string_preserved(self):
        data = {
            'docx-template': {
                'default-template': 'none',
            },
        }
        config = PublishConfig.model_validate(data)
        assert config.docx_template.default_template == 'none'

    def test_docx_template_empty_section(self):
        data = {
            'docx-template': {},
        }
        config = PublishConfig.model_validate(data)
        assert config.docx_template is not None
        assert config.docx_template.default_template is None
        assert config.docx_template.overrides == {}

    def test_docx_template_from_yaml(self, tmp_path):
        yaml_content = """
start_level: 1
docx-template:
  default-template: "templates/corporate.dotm"
  overrides:
    sys-reqs: "templates/sys.dotm"
    impl: "none"
"""
        p = tmp_path / 'publish.yaml'
        p.write_text(yaml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.yaml'), tmp_path)
        assert config.docx_template is not None
        assert config.docx_template.default_template == 'templates/corporate.dotm'
        assert config.docx_template.overrides == {'sys-reqs': 'templates/sys.dotm', 'impl': 'none'}

    def test_docx_template_rejects_extra_fields(self):
        from syntagmax.publish_config import DocxTemplate

        data = {
            'default-template': 'test.dotm',
            'unknown_field': 'value',
        }
        with pytest.raises(ValidationError):
            DocxTemplate.model_validate(data)


class TestContentsMarker:
    def test_default_contents_marker(self):
        config = PublishConfig()
        assert config.contents_marker == '_contents_'

    def test_custom_contents_marker(self):
        config = PublishConfig(contents_marker='_body_')
        assert config.contents_marker == '_body_'

    def test_contents_marker_from_yaml(self, tmp_path):
        yaml_content = """
start_level: 1
contents_marker: "_intro_"
"""
        p = tmp_path / 'publish.yaml'
        p.write_text(yaml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.yaml'), tmp_path)
        assert config.contents_marker == '_intro_'

    def test_contents_marker_rejects_empty(self):
        with pytest.raises(ValidationError):
            PublishConfig(contents_marker='')

    def test_contents_marker_rejects_whitespace(self):
        with pytest.raises(ValidationError):
            PublishConfig(contents_marker='   ')

    def test_contents_marker_rejects_forward_slash(self):
        with pytest.raises(ValidationError):
            PublishConfig(contents_marker='dir/file')

    def test_contents_marker_rejects_backslash(self):
        with pytest.raises(ValidationError):
            PublishConfig(contents_marker='dir\\file')

    def test_contents_marker_accepts_underscores_and_dashes(self):
        config = PublishConfig(contents_marker='--content--')
        assert config.contents_marker == '--content--'


class TestTomlSupport:
    def test_load_publish_config_toml_file(self, tmp_path):
        toml_content = """
start_level = 3

[[render.REQ]]
type = "text"
mode = "inline"

[[render.REQ.attributes]]
[render.REQ.attributes.contents]
alias = "ReqText"
"""
        p = tmp_path / 'publish.toml'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.toml'), tmp_path)
        assert config.start_level == 3
        assert 'REQ' in config.render

    def test_load_publish_config_toml_simple(self, tmp_path):
        toml_content = """
start_level = 2
remove_numeric_prefixes_in_headers = false
include_plain_text = false
"""
        p = tmp_path / 'publish.toml'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.toml'), tmp_path)
        assert config.start_level == 2
        assert config.remove_numeric_prefixes_in_headers is False
        assert config.include_plain_text is False

    def test_load_publish_config_toml_underscore_keys(self, tmp_path):
        toml_content = """
start_level = 1

[docx_template]
default_template = "templates/corporate.dotm"

[docx_template.overrides]
system-requirements = "templates/sys.dotm"
"""
        p = tmp_path / 'publish.toml'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.toml'), tmp_path)
        assert config.docx_template is not None
        assert config.docx_template.default_template == 'templates/corporate.dotm'
        assert config.docx_template.overrides['system-requirements'] == 'templates/sys.dotm'

    def test_load_publish_config_toml_hyphenated_keys(self, tmp_path):
        toml_content = """
start_level = 1

["docx-template"]
"default-template" = "templates/corporate.dotm"

["docx-template".overrides]
sys-reqs = "templates/sys.dotm"
"""
        p = tmp_path / 'publish.toml'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.toml'), tmp_path)
        assert config.docx_template is not None
        assert config.docx_template.default_template == 'templates/corporate.dotm'

    def test_load_publish_config_unknown_extension(self, tmp_path):
        p = tmp_path / 'publish.json'
        p.write_text('{}', encoding='utf-8')
        with pytest.raises(FatalError):
            load_publish_config(Path('publish.json'), tmp_path)

    def test_load_publish_config_case_insensitive_extension(self, tmp_path):
        toml_content = "start_level = 4\n"
        p = tmp_path / 'publish.TOML'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.TOML'), tmp_path)
        assert config.start_level == 4

    def test_load_publish_config_yml_extension(self, tmp_path):
        yaml_content = "start_level: 5\n"
        p = tmp_path / 'publish.yml'
        p.write_text(yaml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.yml'), tmp_path)
        assert config.start_level == 5

    def test_load_publish_config_nonexistent_toml(self, tmp_path):
        config = load_publish_config(Path('nonexistent.toml'), tmp_path)
        assert config.start_level == 1

    def test_load_publish_config_invalid_toml(self, tmp_path):
        p = tmp_path / 'bad.toml'
        p.write_text("start_level = 'not-an-int'", encoding='utf-8')
        with pytest.raises(FatalError):
            load_publish_config(Path('bad.toml'), tmp_path)

    def test_load_publish_config_full_path(self, tmp_path):
        """Test that load_publish_config works with absolute paths."""
        toml_content = "start_level = 7\n"
        p = tmp_path / 'publish.toml'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(p, tmp_path)
        assert config.start_level == 7


class TestResolvePublishFile:
    def test_resolve_publish_file_yaml_only(self, tmp_path):
        (tmp_path / 'publish.yaml').write_text('start_level: 1', encoding='utf-8')
        result = resolve_publish_file(tmp_path)
        assert result == tmp_path / 'publish.yaml'

    def test_resolve_publish_file_yml_only(self, tmp_path):
        (tmp_path / 'publish.yml').write_text('start_level: 1', encoding='utf-8')
        result = resolve_publish_file(tmp_path)
        assert result == tmp_path / 'publish.yml'

    def test_resolve_publish_file_toml_only(self, tmp_path):
        (tmp_path / 'publish.toml').write_text('start_level = 1', encoding='utf-8')
        result = resolve_publish_file(tmp_path)
        assert result == tmp_path / 'publish.toml'

    def test_resolve_publish_file_neither(self, tmp_path):
        result = resolve_publish_file(tmp_path)
        assert result is None

    def test_resolve_publish_file_both_yaml_and_toml_error(self, tmp_path):
        (tmp_path / 'publish.yaml').write_text('start_level: 1', encoding='utf-8')
        (tmp_path / 'publish.toml').write_text('start_level = 1', encoding='utf-8')
        with pytest.raises(FatalError):
            resolve_publish_file(tmp_path)

    def test_resolve_publish_file_yml_and_toml_error(self, tmp_path):
        (tmp_path / 'publish.yml').write_text('start_level: 1', encoding='utf-8')
        (tmp_path / 'publish.toml').write_text('start_level = 1', encoding='utf-8')
        with pytest.raises(FatalError):
            resolve_publish_file(tmp_path)

    def test_resolve_publish_file_yaml_preferred_over_yml(self, tmp_path):
        """When both .yaml and .yml exist (no TOML), .yaml takes precedence."""
        (tmp_path / 'publish.yaml').write_text('start_level: 1', encoding='utf-8')
        (tmp_path / 'publish.yml').write_text('start_level: 2', encoding='utf-8')
        result = resolve_publish_file(tmp_path)
        assert result == tmp_path / 'publish.yaml'

    def test_resolve_publish_file_ignores_directories(self, tmp_path):
        """A directory named publish.yaml should not be detected."""
        (tmp_path / 'publish.yaml').mkdir()
        result = resolve_publish_file(tmp_path)
        assert result is None

    def test_resolve_publish_file_ignores_directory_with_toml_file(self, tmp_path):
        """A directory named publish.yaml should not conflict with publish.toml."""
        (tmp_path / 'publish.yaml').mkdir()
        (tmp_path / 'publish.toml').write_text('start_level = 1', encoding='utf-8')
        result = resolve_publish_file(tmp_path)
        assert result == tmp_path / 'publish.toml'


class TestConfigResolutionToml:
    def test_config_resolution_toml_fallback(self, tmp_path):
        from syntagmax.config import Config
        from syntagmax.params import Params

        cfg_path = tmp_path / 'config.toml'
        cfg_content = """
base = "."
[[input]]
name = "r1"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # Create .syntagmax/publish.toml as fallback
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()
        (dot_syntagmax / 'publish.toml').write_text('start_level = 4', encoding='utf-8')

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        config_r1 = config.load_publish_config(records[0])
        assert config_r1.start_level == 4

    def test_config_resolution_toml_per_record(self, tmp_path):
        from syntagmax.config import Config
        from syntagmax.params import Params

        cfg_path = tmp_path / 'config.toml'
        cfg_content = """
base = "."
[[input]]
name = "r1"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
publish = "custom.toml"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        (tmp_path / 'custom.toml').write_text('start_level = 6', encoding='utf-8')

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        config_r1 = config.load_publish_config(records[0])
        assert config_r1.start_level == 6

    def test_config_resolution_conflict_error(self, tmp_path):
        from syntagmax.config import Config
        from syntagmax.params import Params

        cfg_path = tmp_path / 'config.toml'
        cfg_content = """
base = "."
[[input]]
name = "r1"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # Create both publish.yaml and publish.toml in root
        (tmp_path / 'publish.yaml').write_text('start_level: 1', encoding='utf-8')
        (tmp_path / 'publish.toml').write_text('start_level = 2', encoding='utf-8')

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        with pytest.raises(FatalError):
            config.load_publish_config(records[0])

    def test_config_resolution_root_toml_over_syntagmax_yaml(self, tmp_path):
        """Root publish.toml takes priority over .syntagmax/publish.yaml."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        cfg_path = tmp_path / 'config.toml'
        cfg_content = """
base = "."
[[input]]
name = "r1"
dir = "SYS"
driver = "obsidian"
atype = "SYS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        (tmp_path / 'publish.toml').write_text('start_level = 8', encoding='utf-8')
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()
        (dot_syntagmax / 'publish.yaml').write_text('start_level: 2', encoding='utf-8')

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        config_r1 = config.load_publish_config(records[0])
        assert config_r1.start_level == 8
