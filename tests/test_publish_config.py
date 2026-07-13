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

    # Create default publish.yaml alongside config (auto-discovered in _root_dir)
    default_yaml = tmp_path / 'publish.yaml'
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

    # Resolve for r2 (should fall back to publish.yaml in _root_dir -> start_level=2)
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

        # Create publish.toml alongside config (auto-discovered in _root_dir)
        (tmp_path / 'publish.toml').write_text('start_level = 4', encoding='utf-8')

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

    def test_config_resolution_auto_discovery_ignores_subdirs(self, tmp_path):
        """Auto-discovery only checks _root_dir, not subdirectories."""
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

        # Only _root_dir (tmp_path) is checked; .syntagmax/ subdirectory is ignored
        config_r1 = config.load_publish_config(records[0])
        assert config_r1.start_level == 8


class TestPublishResolutionWithBaseDir:
    """Tests for publish config resolution when config file is in a subdirectory with base='..'."""

    def test_per_record_publish_resolves_relative_to_base_dir(self, tmp_path):
        """Bug scenario: config at .syntagmax/config.toml, base='..', publish='publish.yaml' at project root."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        # Create project layout: project_root/.syntagmax/config.toml
        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."

[[input]]
name = "SCHED"
dir = "Personal Scheduler App"
driver = "obsidian"
atype = "SRS"
marker = "REQ"
publish = "publish.yaml"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # publish.yaml is at the project root (where base points)
        publish_yaml = project_root / 'publish.yaml'
        publish_yaml.write_text('start_level: 4', encoding='utf-8')

        # Create the input dir so Config doesn't error
        (project_root / 'Personal Scheduler App').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        assert len(records) == 1
        assert records[0].publish_config == 'publish.yaml'

        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 4

    def test_explicit_publish_not_found_raises_error(self, tmp_path):
        """When publish is explicitly specified but file doesn't exist, raise FatalError."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."

[[input]]
name = "SCHED"
dir = "docs"
driver = "obsidian"
atype = "SRS"
publish = "publish.yaml"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        (project_root / 'docs').mkdir()
        # Deliberately NOT creating publish.yaml

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        with pytest.raises(FatalError, match="Publish config file not found"):
            config.load_publish_config(records[0])

    def test_base_dir_publish_not_auto_discovered(self, tmp_path):
        """publish.yaml in base_dir is NOT auto-discovered (base_dir is for input records, not config)."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # publish.yaml in project root (base_dir) — should NOT be auto-discovered
        (project_root / 'publish.yaml').write_text('start_level: 7', encoding='utf-8')
        (project_root / 'docs').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        # Should get defaults since base_dir is not checked for auto-discovery
        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 1

    def test_fallback_finds_publish_in_syntagmax_subdir(self, tmp_path):
        """Auto-discovery finds publish.yaml in the config file's directory (.syntagmax/)."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # publish.yaml in .syntagmax/ (not in project root)
        (dot_syntagmax / 'publish.yaml').write_text('start_level: 3', encoding='utf-8')
        (project_root / 'docs').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 3

    def test_syntagmax_dir_auto_discovery_ignores_base_dir(self, tmp_path):
        """Auto-discovery only checks _root_dir (.syntagmax/), not base_dir."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # publish.yaml in both locations — only .syntagmax/ should be used
        (project_root / 'publish.yaml').write_text('start_level: 9', encoding='utf-8')
        (dot_syntagmax / 'publish.yaml').write_text('start_level: 2', encoding='utf-8')
        (project_root / 'docs').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 2

    def test_load_publish_config_explicit_nonexistent_raises(self, tmp_path):
        """load_publish_config with explicit=True raises FatalError for missing file."""
        with pytest.raises(FatalError, match="Publish config file not found"):
            load_publish_config(Path('nonexistent.yaml'), tmp_path, explicit=True)

    def test_load_publish_config_non_explicit_nonexistent_returns_defaults(self, tmp_path):
        """load_publish_config without explicit=True returns defaults for missing file."""
        config = load_publish_config(Path('nonexistent.yaml'), tmp_path)
        assert config.start_level == 1



class TestGlobalPublishConfig:
    """Tests for the top-level 'publish' field in config.toml."""

    def test_global_publish_used_when_no_per_record(self, tmp_path):
        """Global publish field is used when no per-record publish is set."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."
publish = "my-publish.yaml"

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # Resolved relative to config file dir (.syntagmax/)
        (dot_syntagmax / 'my-publish.yaml').write_text('start_level: 6', encoding='utf-8')
        (project_root / 'docs').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 6

    def test_per_record_overrides_global(self, tmp_path):
        """Per-record publish takes priority over global publish."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."
publish = "global-publish.yaml"

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
publish = "record-publish.yaml"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # Global resolves relative to config dir (.syntagmax/)
        (dot_syntagmax / 'global-publish.yaml').write_text('start_level: 2', encoding='utf-8')
        # Per-record resolves relative to base_dir (project_root)
        (project_root / 'record-publish.yaml').write_text('start_level: 8', encoding='utf-8')
        (project_root / 'docs').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 8

    def test_global_publish_overrides_auto_discovery(self, tmp_path):
        """Global publish takes priority over auto-discovered publish files."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."
publish = "custom-publish.yaml"

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # Auto-discoverable file in .syntagmax/ (would be found by convention)
        (dot_syntagmax / 'publish.yaml').write_text('start_level: 3', encoding='utf-8')
        # Explicit global publish file (also in .syntagmax/, different name)
        (dot_syntagmax / 'custom-publish.yaml').write_text('start_level: 5', encoding='utf-8')
        (project_root / 'docs').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 5

    def test_global_publish_missing_raises_error(self, tmp_path):
        """Global publish field pointing to nonexistent file raises FatalError."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."
publish = "nonexistent.yaml"

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')
        (project_root / 'docs').mkdir()
        # Deliberately NOT creating nonexistent.yaml in .syntagmax/

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        with pytest.raises(FatalError, match="Publish config file not found"):
            config.load_publish_config(records[0])

    def test_global_publish_not_set_falls_through(self, tmp_path):
        """When global publish is not set, auto-discovery in .syntagmax/ is used."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        project_root = tmp_path / 'project'
        project_root.mkdir()
        dot_syntagmax = project_root / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg_path = dot_syntagmax / 'config.toml'
        cfg_content = """
base = ".."

[[input]]
name = "r1"
dir = "docs"
driver = "obsidian"
atype = "SRS"
"""
        cfg_path.write_text(cfg_content, encoding='utf-8')

        # Auto-discoverable in .syntagmax/ (config file's directory)
        (dot_syntagmax / 'publish.yaml').write_text('start_level: 4', encoding='utf-8')
        (project_root / 'docs').mkdir()

        params = Params(verbose=False, render_tree=False, ai=False, output='console')
        config = Config(params=params, config_filename=cfg_path)
        records = config.input_records()

        pub_config = config.load_publish_config(records[0])
        assert pub_config.start_level == 4


class TestTableSpacer:
    """Tests for the table_spacer global and per-section spacer fields."""

    def test_default_table_spacer(self):
        config = PublishConfig()
        assert config.table_spacer == 1

    def test_custom_table_spacer(self):
        config = PublishConfig.model_validate({'table_spacer': 3})
        assert config.table_spacer == 3

    def test_table_spacer_kebab_case_alias(self):
        config = PublishConfig.model_validate({'table-spacer': 5})
        assert config.table_spacer == 5

    def test_table_spacer_zero(self):
        config = PublishConfig.model_validate({'table_spacer': 0})
        assert config.table_spacer == 0

    def test_table_spacer_max_value(self):
        config = PublishConfig.model_validate({'table_spacer': 20})
        assert config.table_spacer == 20

    def test_table_spacer_rejects_negative(self):
        with pytest.raises(ValidationError):
            PublishConfig.model_validate({'table_spacer': -1})

    def test_table_spacer_rejects_over_max(self):
        with pytest.raises(ValidationError):
            PublishConfig.model_validate({'table_spacer': 21})

    def test_table_spacer_rejects_non_integer(self):
        with pytest.raises(ValidationError):
            PublishConfig.model_validate({'table_spacer': 'abc'})

    def test_table_spacer_from_yaml(self, tmp_path):
        yaml_content = "table_spacer: 4\n"
        p = tmp_path / 'publish.yaml'
        p.write_text(yaml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.yaml'), tmp_path)
        assert config.table_spacer == 4

    def test_table_spacer_kebab_from_yaml(self, tmp_path):
        yaml_content = "table-spacer: 3\n"
        p = tmp_path / 'publish.yaml'
        p.write_text(yaml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.yaml'), tmp_path)
        assert config.table_spacer == 3

    def test_table_spacer_from_toml(self, tmp_path):
        toml_content = "table_spacer = 5\n"
        p = tmp_path / 'publish.toml'
        p.write_text(toml_content, encoding='utf-8')
        config = load_publish_config(Path('publish.toml'), tmp_path)
        assert config.table_spacer == 5

    def test_table_section_spacer_default_none(self):
        sec = TableSection.model_validate({'type': 'table', 'attributes': [{'id': {'alias': 'ID'}}]})
        assert sec.spacer is None

    def test_table_section_spacer_set(self):
        sec = TableSection.model_validate({'type': 'table', 'spacer': 2, 'attributes': [{'id': {'alias': 'ID'}}]})
        assert sec.spacer == 2

    def test_table_section_spacer_zero(self):
        sec = TableSection.model_validate({'type': 'table', 'spacer': 0, 'attributes': [{'id': {'alias': 'ID'}}]})
        assert sec.spacer == 0

    def test_table_section_spacer_max(self):
        sec = TableSection.model_validate({'type': 'table', 'spacer': 20, 'attributes': [{'id': {'alias': 'ID'}}]})
        assert sec.spacer == 20

    def test_table_section_spacer_rejects_negative(self):
        with pytest.raises(ValidationError):
            TableSection.model_validate({'type': 'table', 'spacer': -1, 'attributes': [{'id': {'alias': 'ID'}}]})

    def test_table_section_spacer_rejects_over_max(self):
        with pytest.raises(ValidationError):
            TableSection.model_validate({'type': 'table', 'spacer': 21, 'attributes': [{'id': {'alias': 'ID'}}]})

    def test_table_section_spacer_rejects_non_integer(self):
        with pytest.raises(ValidationError):
            TableSection.model_validate({'type': 'table', 'spacer': 'big', 'attributes': [{'id': {'alias': 'ID'}}]})
