# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Configuration for the Syntagmax RMS.

import os
import re
from pathlib import Path
import tomllib
import logging as lg
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from syntagmax.publish_config import PublishConfig
import json
from dataclasses import dataclass, field

from benedict import benedict
from pydantic import BaseModel, ConfigDict, Field, field_validator

from syntagmax.params import Params
from syntagmax.metamodel import load_metamodel
from syntagmax.errors import FatalError
from syntagmax.plugin import PluginConfig


VALID_EXCLUDE_ELEMENTS = frozenset({'callouts', 'headings', 'horizontal_rules', 'frontmatter', 'tags'})
VALID_EXCLUDE_MODES = frozenset({'only', 'string', 'string-on-start'})


class ExcludeElementConfig(BaseModel):
    """Configuration for a single element exclusion with removal mode."""

    name: str = Field(..., description='Element name to exclude')
    mode: str = Field(default='string-on-start', description='Removal mode: only, string, or string-on-start')

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if v not in VALID_EXCLUDE_ELEMENTS:
            raise ValueError(f'Unknown exclude element "{v}". Valid elements: {sorted(VALID_EXCLUDE_ELEMENTS)}')
        return v

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in VALID_EXCLUDE_MODES:
            raise ValueError(f'Unknown exclude mode "{v}". Valid modes: {sorted(VALID_EXCLUDE_MODES)}')
        return v


def _validate_no_duplicate_elements(v: list[ExcludeElementConfig]) -> list[ExcludeElementConfig]:
    """Container-level validator rejecting duplicate element names."""
    seen: set[str] = set()
    for elem in v:
        if elem.name in seen:
            raise ValueError(f'Duplicate exclude element "{elem.name}" in exclude_elements list')
        seen.add(elem.name)
    return v


VALID_STRICT_LINE_BREAKS_VALUES = frozenset({'on', 'true', 'off', 'false', 'auto'})


class ObsidianDriverConfig(BaseModel):
    exclude_elements: list[ExcludeElementConfig] = Field(default_factory=list, description='Markdown elements to exclude at extraction time')
    integration: bool = Field(default=False, description='Enable reading Obsidian vault settings (e.g. attachmentFolderPath)')
    root: str | None = Field(default=None, description='Override path to the .obsidian directory (relative to base dir)')
    strict_line_breaks: str | bool = Field(
        default='on',
        description='Line break mode: on/true (standard Markdown), off/false (Obsidian relaxed), auto (read from app.json)',
    )

    @field_validator('strict_line_breaks', mode='before')
    @classmethod
    def validate_strict_line_breaks(cls, v: str | bool) -> str:
        if isinstance(v, bool):
            return 'true' if v else 'false'
        normalized = str(v).lower().strip()
        if normalized not in VALID_STRICT_LINE_BREAKS_VALUES:
            raise ValueError(f'Invalid strict_line_breaks value "{v}". Valid values: {sorted(VALID_STRICT_LINE_BREAKS_VALUES)}')
        return normalized

    @field_validator('exclude_elements')
    @classmethod
    def validate_exclude_elements(cls, v: list[ExcludeElementConfig]) -> list[ExcludeElementConfig]:
        return _validate_no_duplicate_elements(v)


class DriversConfig(BaseModel):
    obsidian: ObsidianDriverConfig = Field(default_factory=ObsidianDriverConfig)


@dataclass
class InputRecord:
    name: str
    dir: str
    record_base: Path
    filepaths: list[Path]
    driver: str
    default_atype: str
    marker: str
    filter_glob: str = '**/*'
    markers: list[str] = field(default_factory=list)
    publish_config: str | None = None
    exclude_elements: list['ExcludeElementConfig'] = field(default_factory=list)


DEFAULT_FILTERS = {'obsidian': '**/*.md', 'ipynb': '**/*.ipynb', 'markdown': '**/*.md'}


class InputConfig(BaseModel):
    name: str = Field(..., description='Input source name (e.g., "requirements")')
    dir: str = Field(..., description='Subdirectory relative to the base directory where artifacts are located')
    driver: str = Field(..., description='Driver type for processing (e.g., "obsidian", "text")')
    filter: str | None = Field(default=None, description='File filter pattern (glob). If omitted, driver-specific defaults are used.')
    atype: str = Field('REQ', description='Default artifact type for this input source')
    marker: str | None = Field(default=None, description='Custom marker for artifacts (e.g., "REQ"). Defaults to atype.')
    markers: list[str] = Field(default_factory=list, description='Fragment markers for non-artifact text blocks (e.g., ["COM", "NOTE"]). Obsidian driver only.')
    publish: str | None = Field(default=None, description='Path to publish config file relative to the base directory. Error if not found.')
    exclude_elements: list[ExcludeElementConfig] | None = Field(
        default=None, description='Markdown elements to exclude at extraction time (merged with global driver defaults)'
    )

    @field_validator('exclude_elements')
    @classmethod
    def validate_exclude_elements(cls, v: list[ExcludeElementConfig] | None) -> list[ExcludeElementConfig] | None:
        if v is None:
            return v
        return _validate_no_duplicate_elements(v)


class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    enabled: bool = Field(default=False, description='Enable metrics collection')
    requirement_type: str = Field(default='REQ', description='The artifact type to treat as a "requirement" for metrics')
    status_field: str = Field(default='status', description='Name of the attribute used to track artifact status')
    verify_field: str = Field(default='verify', description='Name of the attribute used to track verification status')
    tbd_marker: str = Field(default='TBD', description='String marker used to identify "To Be Defined" items')


class ImpactConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    enabled: bool = Field(default=False, description='Enable impact analysis')


class AIConfig(BaseModel):
    provider: str = Field(default='ollama', description='AI provider to use (ollama, anthropic, openai, gemini, bedrock)')
    model: str | None = Field(default=None, description='Model name to use (e.g., "gpt-4o", "claude-3-5-sonnet")')
    # Provider-specific configurations
    anthropic_api_key: str | None = Field(default=None, description='Anthropic API Key. Can also be set via ANTHROPIC_API_KEY env var.')
    openai_api_key: str | None = Field(default=None, description='OpenAI API Key. Can also be set via OPENAI_API_KEY env var.')
    gemini_api_key: str | None = Field(default=None, description='Google Gemini API Key. Can also be set via GEMINI_API_KEY env var.')
    aws_access_key_id: str | None = Field(default=None, description='AWS Access Key ID for Bedrock.')
    aws_secret_access_key: str | None = Field(default=None, description='AWS Secret Access Key for Bedrock.')
    aws_session_token: str | None = Field(default=None, description='AWS Session Token for Bedrock (optional).')
    aws_region_name: str | None = Field(default=None, description='AWS Region for Bedrock (e.g., "us-east-1").')
    aws_api_key: str | None = Field(default=None, description='AWS Bedrock API Key (if applicable).')
    ollama_host: str = Field(default='http://localhost:11434', description='Host URL for the Ollama API')
    timeout_s: float = Field(default=60.0, description='Timeout in seconds for AI provider requests')


class TraceConfig(BaseModel):
    """Configuration for trace export."""

    plugins: list[str] = Field(default_factory=list, description='List of plugin names to run for trace export')


class BaselineConfig(BaseModel):
    """Configuration for the baseline tagging command."""

    tag_pattern: str | None = Field(default=None, description='Optional regex pattern that tag names must match')

    @field_validator('tag_pattern')
    @classmethod
    def validate_tag_pattern(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f'Invalid tag_pattern regex "{v}": {e}')
        return v


class Metamodel(BaseModel):
    filename: str = Field(default=None, description='Path to the .syntagmax file defining the project metamodel')


class ConfigFile(BaseModel):
    base: str = Field(default='..', description='Base directory for relative paths, relative to this config file')
    language: str = Field(default='en', description='Output language for reports (en, ru)')
    publish: str | None = Field(default=None, description='Global publish config file path, relative to config file directory')
    input: list[InputConfig] = Field(..., description='List of input sources to process')
    metrics: MetricsConfig = Field(MetricsConfig(), description='Configuration for metrics collection')
    impact: ImpactConfig = Field(ImpactConfig(), description='Configuration for impact analysis')
    metamodel: Metamodel = Field(Metamodel(), description='Configuration for the artifact metamodel')
    ai: AIConfig = Field(default_factory=AIConfig, description='Configuration for AI-powered analysis')
    plugin: list[PluginConfig] = Field(default_factory=list, description='List of plugin configurations')
    drivers: DriversConfig = Field(default_factory=DriversConfig, description='Driver-specific configuration defaults')
    baseline: BaselineConfig = Field(default_factory=BaselineConfig, description='Configuration for the baseline tagging command')
    trace: TraceConfig = Field(default_factory=TraceConfig, description='Configuration for trace export')

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        from syntagmax.i18n import SUPPORTED_LANGUAGES

        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language '{v}'. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}")
        return v


class Config:
    params: Params
    metrics: MetricsConfig
    impact: ImpactConfig
    ai: AIConfig

    def __init__(self, params: Params, config_filename: Path):
        self.params = params
        self._root_dir = Path(config_filename).parent.absolute()
        self.metrics = MetricsConfig()
        self.impact = ImpactConfig()
        self.ai = AIConfig()
        self._input_records: list[InputRecord] = []
        self._plugins = []
        self._read_config(config_filename)

    def _read_config(self, config_filename: Path):
        errors: list[str] = []

        config_file = Path(config_filename)
        lg.info(f'Using configuration file: {config_file}')

        # Note: Root directory is the directory of the config file
        # Base directory is relative to the root directory, where
        # artifacts are located.
        root_dir = config_file.parent
        config_data = benedict()

        try:
            # Global config
            global_config_path = Path(os.path.expanduser('~/.config/syntagmax/config.toml'))

            if global_config_path.exists():
                lg.info(f'Loading global configuration from {global_config_path}')
                global_data = tomllib.loads(global_config_path.read_text(encoding='utf-8'))
                config_data.merge(global_data)
        except Exception as e:
            errors.append(f'Failed to load global config: {e}')
            raise FatalError(errors)

        try:
            # Project config
            project_data = tomllib.loads(config_file.read_text(encoding='utf-8'))
            config_data.merge(project_data)
        except Exception as exc:
            errors.append(f'Failed to load project config: {exc}')

        if self.params['verbose']:
            json_config = json.dumps(config_data, indent=4)
            lg.debug(f'Configuration file contents: {json_config}')

        if errors:
            raise FatalError(errors)

        config_model = ConfigFile.model_validate(config_data)

        lg.debug(f'Root directory: {root_dir}. Base directory: {config_model.base}')

        self._base_dir = Path(root_dir, config_model.base)
        lg.debug(f'Base directory: {self._base_dir}')
        self._global_publish_config = config_model.publish
        self._read_input_records(config_model.input, config_model.drivers)

        self.metrics = config_model.metrics
        self.impact = config_model.impact
        self.ai = config_model.ai
        self._obsidian_driver_config = config_model.drivers.obsidian
        self._baseline_config = config_model.baseline
        self._trace_config = config_model.trace

        # Resolve language: CLI --lang > config language > default 'en'
        from syntagmax.i18n import setup_i18n

        self.language = self.params.get('language') or config_model.language or 'en'
        setup_i18n(self.language)

        # Validate strict_line_breaks = "auto" requires integration = true
        if self._obsidian_driver_config.strict_line_breaks == 'auto' and not self._obsidian_driver_config.integration:
            errors.append('strict_line_breaks = "auto" requires integration = true in [drivers.obsidian]')

        if config_model.metamodel.filename:
            self.metamodel = load_metamodel(Path(root_dir, config_model.metamodel.filename), errors)
        else:
            lg.warning('No static validation model')
            self.metamodel = None

        # Validate fragment markers don't collide with metamodel attributes
        if self.metamodel:
            self._validate_marker_attribute_collisions(errors)

        if errors:
            raise FatalError(errors)

        # Load plugins
        from syntagmax.plugin import load_plugins

        self._plugins = load_plugins(config_model.plugin, self._root_dir)

    def _read_input_records(self, input_configs: list[InputConfig], drivers: DriversConfig):
        errors: list[str] = []

        for input_config in input_configs:
            name = input_config.name
            record_base = Path(self._base_dir, input_config.dir)
            glob = input_config.filter or '**/*'

            if not input_config.filter and input_config.driver in DEFAULT_FILTERS:
                lg.info(f'Using default filter ({DEFAULT_FILTERS[input_config.driver]}) for {record_base}')
                glob = DEFAULT_FILTERS[input_config.driver]

            lg.debug(f'Adding input files from {name} with filter {glob}')
            filepaths = Path(record_base).glob(glob)

            artifact_marker = input_config.marker or input_config.atype
            fragment_markers = input_config.markers

            # Resolve exclude_elements: union of global driver default and record-level
            # Per-record mode takes precedence when both define the same element name
            global_excludes: list[ExcludeElementConfig] = []
            if input_config.driver == 'obsidian':
                global_excludes = drivers.obsidian.exclude_elements
            record_excludes = input_config.exclude_elements or []

            # Merge: start with global, then overlay per-record (per-record wins on conflict)
            merged: dict[str, ExcludeElementConfig] = {}
            for elem in global_excludes:
                merged[elem.name] = elem
            for elem in record_excludes:
                merged[elem.name] = elem
            resolved_excludes = sorted(merged.values(), key=lambda e: e.name)

            # Validate fragment markers
            if fragment_markers:
                if input_config.driver != 'obsidian':
                    errors.append(f'Input "{name}": markers are only supported for the obsidian driver, got driver "{input_config.driver}"')

                marker_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
                seen_markers: set[str] = set()

                for m in fragment_markers:
                    if not m:
                        errors.append(f'Input "{name}": marker names must not be empty')
                        continue

                    if not marker_pattern.match(m):
                        errors.append(f'Input "{name}": invalid marker name "{m}" (must match ^[a-zA-Z0-9_-]+$)')
                        continue

                    m_upper = m.upper()

                    if m_upper in seen_markers:
                        errors.append(f'Input "{name}": duplicate marker "{m}" (case-insensitive)')
                    seen_markers.add(m_upper)

                    if m_upper == artifact_marker.upper():
                        errors.append(f'Input "{name}": fragment marker "{m}" collides with artifact marker "{artifact_marker}"')

            self._input_records.append(
                InputRecord(
                    name=name,
                    dir=input_config.dir,
                    record_base=record_base,
                    filepaths=list(filepaths),
                    driver=input_config.driver,
                    default_atype=input_config.atype,
                    marker=artifact_marker,
                    filter_glob=glob,
                    markers=[m.upper() for m in fragment_markers],
                    publish_config=input_config.publish,
                    exclude_elements=resolved_excludes,
                )
            )

        if errors:
            raise FatalError(errors)

        for input_record in self._input_records:
            lg.info(f'Input record: {input_record.name}')
            lg.debug(f'Input files: {len(input_record.filepaths)}')

    def _validate_marker_attribute_collisions(self, errors: list[str]):
        """Validate that configured fragment markers do not collide with metamodel attribute names."""
        artifacts_meta = self.metamodel.get('artifacts', {})

        for record in self._input_records:
            if not record.markers:
                continue

            # Get attribute names for this record's artifact type
            atype = record.default_atype
            atype_meta = artifacts_meta.get(atype, {})
            attr_names = set()

            if 'attributes' in atype_meta:
                for attr_name in atype_meta['attributes'].keys():
                    attr_names.add(attr_name.upper())

            # Check collision
            for marker in record.markers:
                if marker.upper() in attr_names:
                    errors.append(
                        f'Input "{record.name}": fragment marker "{marker}" collides with metamodel attribute "{marker.lower()}" for artifact type "{atype}"'
                    )

    def load_publish_config(self, record: InputRecord) -> 'PublishConfig':
        from syntagmax.publish_config import load_publish_config, resolve_publish_file

        if record.publish_config:
            p = Path(record.publish_config)
            return load_publish_config(p, self._base_dir, explicit=True)

        # Fallback chain (documented resolution order):
        # 1. Global publish field in config.toml (resolved relative to config file dir)
        if self._global_publish_config:
            p = Path(self._global_publish_config)
            return load_publish_config(p, self._root_dir, explicit=True)

        # 2. Auto-discover publish.yaml/yml/toml in .syntagmax directory
        resolved = resolve_publish_file(self._root_dir)
        if resolved:
            return load_publish_config(resolved, self._root_dir)

        # 3. All-default rendering
        return load_publish_config(None, self._root_dir)

    def root_dir(self) -> Path:
        return self._root_dir

    def base_dir(self):
        return self._base_dir

    def derive_path(self, path: Path) -> str:
        rel_path = path.absolute().relative_to(self._base_dir.absolute())
        return rel_path.as_posix()

    def input_records(self) -> list[InputRecord]:
        return self._input_records

    def plugins(self):
        return self._plugins

    @property
    def trace_plugins(self) -> list[str]:
        return self._trace_config.plugins

    @property
    def obsidian_driver_config(self) -> 'ObsidianDriverConfig':
        return self._obsidian_driver_config

    @property
    def baseline_config(self) -> 'BaselineConfig':
        return self._baseline_config

    def resolve_strict_line_breaks(self) -> bool:
        """Resolve the effective strict_line_breaks setting to a boolean.

        Returns:
            True if strict mode is ON (standard Markdown, no transformation).
            False if strict mode is OFF (Obsidian relaxed breaks, apply transformation).
        """
        if hasattr(self, '_strict_line_breaks_resolved'):
            return self._strict_line_breaks_resolved

        value = self._obsidian_driver_config.strict_line_breaks
        if value in ('on', 'true'):
            result = True
            lg.info(f'Strict line breaks: ON (configured as "{value}") - standard Markdown, no transformation')
        elif value in ('off', 'false'):
            result = False
            lg.info(f'Strict line breaks: OFF (configured as "{value}") - Obsidian relaxed breaks, applying hard break transformation')
        else:
            # auto mode — read from app.json
            from syntagmax.obsidian_settings import read_obsidian_strict_line_breaks

            obsidian_value = read_obsidian_strict_line_breaks(self._base_dir, self._obsidian_driver_config.root)
            if obsidian_value is None:
                lg.warning('Could not read strictLineBreaks from Obsidian settings, defaulting to strict mode ON')
                result = True
                lg.info('Strict line breaks: ON (auto, fallback) - standard Markdown, no transformation')
            else:
                result = obsidian_value
                mode_str = 'ON' if result else 'OFF'
                effect = 'no transformation' if result else 'applying hard break transformation'
                lg.info(f'Strict line breaks: {mode_str} (auto, read from app.json) - {effect}')

        self._strict_line_breaks_resolved = result
        return result

    def get_trace_mode(self, source_atype: str, target_atype: str) -> str:
        if not self.metamodel:
            return 'timestamp'

        traces = self.metamodel.get('traces', {}).get(source_atype, [])
        for trace in traces:
            if target_atype in trace.get('targets', []):
                return trace.get('mode', 'timestamp')

        return 'timestamp'
