# SPDX-License-Identifier: MIT
import pytest
from pathlib import Path
from pydantic import ValidationError
from syntagmax.publish_config import PublishConfig, load_publish_config, TableSection, TextSection, MarkerRenderSection
from syntagmax.errors import FatalError


def test_default_publish_config():
    config = PublishConfig()
    assert config.start_level == 1
    assert config.remove_numeric_prefixes_in_headers is True
    assert config.include_plain_text is True
    assert config.ignore_plain_text_prefixes == []
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
