# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-02
# Description: Publishing Configuration System Model and Loader.

from pathlib import Path
from typing import Literal, Union
import yaml
from pydantic import BaseModel, Field, field_validator, ConfigDict


class DocxTemplate(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    default_template: str | None = Field(default=None, alias='default-template')
    overrides: dict[str, str] = Field(default_factory=dict)


class AttributeRender(BaseModel):
    alias: str


class TableSection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['table']
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
    ignore_plain_text_prefixes: list[str] = Field(default_factory=list)
    render: dict[str, list[RenderSection]] = Field(default_factory=dict)
    docx_template: DocxTemplate | None = Field(default=None, alias='docx-template')


def load_publish_config(path: Path | None, root_dir: Path) -> PublishConfig:
    if path is None:
        return PublishConfig()

    resolved_path = Path(root_dir, path)
    if not resolved_path.exists():
        return PublishConfig()

    try:
        content = resolved_path.read_text(encoding='utf-8')
        data = yaml.safe_load(content) or {}
        return PublishConfig.model_validate(data)
    except Exception as e:
        from syntagmax.errors import FatalError

        raise FatalError([f"Failed to load publish config from '{resolved_path}': {e}"])
