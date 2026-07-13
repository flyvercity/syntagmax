# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-02
# Description: Publishing Configuration System Model and Loader.

from pathlib import Path
from typing import Literal, Union
import tomllib
import yaml
from pydantic import BaseModel, Field, field_validator, ConfigDict


AttributePresence = Literal['all', 'mandatory', 'values-only']


class DocxTemplate(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    default_template: str | None = Field(default=None, alias='default-template')
    overrides: dict[str, str] = Field(default_factory=dict)


class AttributeRender(BaseModel):
    alias: str


class TableSection(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    type: Literal['table']
    spacer: int | None = Field(default=None, ge=0, le=20)
    attribute_presence: AttributePresence | None = Field(default=None, alias='attribute-presence')
    attributes: list[dict[str, AttributeRender]]

    @field_validator('attributes')
    @classmethod
    def validate_single_key_dict(cls, v: list[dict[str, AttributeRender]]) -> list[dict[str, AttributeRender]]:
        for d in v:
            if len(d) != 1:
                raise ValueError('Each dictionary in the attributes list must contain exactly one key (the attribute name)')
        return v


class TextSection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['text']
    mode: Literal['block', 'inline']
    attributes: list[dict[str, AttributeRender]]

    @field_validator('attributes')
    @classmethod
    def validate_single_key_dict(cls, v: list[dict[str, AttributeRender]]) -> list[dict[str, AttributeRender]]:
        for d in v:
            if len(d) != 1:
                raise ValueError('Each dictionary in the attributes list must contain exactly one key (the attribute name)')
        return v


class MarkerRenderSection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['text']
    mode: Literal['block', 'inline']
    alias: str


# Union type for discriminated union in list
RenderSection = Union[TableSection, TextSection, MarkerRenderSection]


class PublishConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    start_level: int = Field(default=1)
    remove_numeric_prefixes_in_headers: bool = Field(default=True)
    include_plain_text: bool = Field(default=True)
    contents_marker: str = Field(default='_contents_', description='Filename marker for headingless content files in publishing')
    table_spacer: int = Field(default=1, alias='table-spacer', ge=0, le=20)
    attribute_presence: AttributePresence = Field(default='values-only', alias='attribute-presence')
    render: dict[str, list[RenderSection]] = Field(default_factory=dict)
    docx_template: DocxTemplate | None = Field(default=None, alias='docx-template')

    @field_validator('contents_marker')
    @classmethod
    def validate_contents_marker(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('contents_marker must be a non-empty, non-whitespace string')
        if '/' in v or '\\' in v:
            raise ValueError('contents_marker must not contain directory separators (/ or \\)')
        return v


def load_publish_config(path: Path | None, root_dir: Path, *, explicit: bool = False) -> PublishConfig:
    if path is None:
        return PublishConfig()

    resolved_path = Path(root_dir, path) if not path.is_absolute() else path
    if not resolved_path.is_file():
        if explicit:
            from syntagmax.errors import FatalError

            raise FatalError([f"Publish config file not found: '{resolved_path}' (specified as '{path}' in input record)"])
        return PublishConfig()

    try:
        content = resolved_path.read_text(encoding='utf-8')
        suffix = resolved_path.suffix.lower()

        if suffix in ('.yaml', '.yml'):
            data = yaml.safe_load(content) or {}
        elif suffix == '.toml':
            data = tomllib.loads(content)
        else:
            from syntagmax.errors import FatalError

            raise FatalError([f"Unsupported publish config format '{suffix}' for '{resolved_path}'. Use .yaml, .yml, or .toml."])

        return PublishConfig.model_validate(data)
    except Exception as e:
        from syntagmax.errors import FatalError

        if isinstance(e, FatalError):
            raise
        raise FatalError([f"Failed to load publish config from '{resolved_path}': {e}"])


def resolve_publish_file(directory: Path) -> Path | None:
    """Check a directory for publish config files with conflict detection.

    Looks for publish.yaml, publish.yml, and publish.toml. If both a YAML
    variant and a TOML variant exist, raises a FatalError. Otherwise returns
    the full resolved path of the found file, or None if no file exists.
    """
    yaml_path = directory / 'publish.yaml'
    yml_path = directory / 'publish.yml'
    toml_path = directory / 'publish.toml'

    has_yaml = yaml_path.is_file()
    has_yml = yml_path.is_file()
    has_toml = toml_path.is_file()

    if (has_yaml or has_yml) and has_toml:
        from syntagmax.errors import FatalError

        yaml_name = 'publish.yaml' if has_yaml else 'publish.yml'
        raise FatalError([f"Both {yaml_name} and publish.toml found in '{directory}'. Please use only one."])

    if has_yaml:
        return yaml_path
    if has_yml:
        return yml_path
    if has_toml:
        return toml_path
    return None
