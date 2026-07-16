# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-02
# Description: Plugin system for Syntagmax - configuration, loading, and execution.

import importlib.metadata
import importlib.util
import logging as lg
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from syntagmax.blocks import Block, BlockTree
from syntagmax.errors import FatalError


class PluginConfig(BaseModel):
    """Configuration for a single plugin."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., description='Plugin name (used for discovery)')
    source: Literal['local', 'package'] = Field(..., description='Plugin source: "local" or "package"')
    enabled: bool = Field(default=True, description='Whether the plugin is active')
    params: dict = Field(default_factory=dict, description='Plugin-specific parameters')

    @field_validator('name')
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if v in {'.', '..'} or '/' in v or '\\' in v:
            raise ValueError('Plugin name must not contain path separators')
        return v


@dataclass
class LoadedPlugin:
    """A loaded plugin module with its configuration."""

    name: str
    module: ModuleType
    params: dict


def load_plugin(plugin_config: PluginConfig, root_dir: Path) -> ModuleType:
    """Load a single plugin module by its configuration.

    Args:
        plugin_config: The plugin configuration block.
        root_dir: The root directory of the project (directory containing config.toml).

    Returns:
        The loaded module.

    Raises:
        FatalError: If the plugin cannot be found or loaded.
    """
    name = plugin_config.name

    if plugin_config.source == 'local':
        return _load_local_plugin(name, root_dir)
    elif plugin_config.source == 'package':
        return _load_package_plugin(name)
    else:
        raise FatalError(f'Plugin "{name}": unknown source "{plugin_config.source}"')


def _load_local_plugin(name: str, root_dir: Path) -> ModuleType:
    """Load a local plugin from the plugins directory."""
    plugins_dir = root_dir / 'plugins'

    # Try single file first
    single_file = plugins_dir / f'{name}.py'
    if single_file.is_file():
        return _load_module_from_file(name, single_file)

    # Try directory package
    package_init = plugins_dir / name / '__init__.py'
    if package_init.is_file():
        return _load_module_from_file(name, package_init)

    raise FatalError(f'Plugin "{name}": local plugin not found. Expected "{single_file}" or "{package_init}"')


def _load_module_from_file(name: str, filepath: Path) -> ModuleType:
    """Load a Python module from a file path, registering it under a clean namespace."""
    module_name = f'syntagmax.plugins.local.{name}'

    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            raise FatalError(f'Plugin "{name}": failed to create module spec from "{filepath}"')

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except FatalError:
        raise
    except Exception as e:
        lg.debug(f'Plugin "{name}" load error:\n{traceback.format_exc()}')
        raise FatalError(f'Plugin "{name}": failed to load from "{filepath}": {e}')


def _load_package_plugin(name: str) -> ModuleType:
    """Load a package plugin via entry-points."""
    try:
        eps = importlib.metadata.entry_points(group='syntagmax.plugins', name=name)
        ep_list = list(eps)
    except Exception as e:
        raise FatalError(f'Plugin "{name}": error querying entry-points: {e}')

    if not ep_list:
        raise FatalError(
            f'Plugin "{name}": no package entry-point found in group "syntagmax.plugins". Ensure the plugin package is installed in the current environment.'
        )

    ep = ep_list[0]

    try:
        module = ep.load()
    except Exception as e:
        lg.debug(f'Plugin "{name}" load error:\n{traceback.format_exc()}')
        raise FatalError(f'Plugin "{name}": failed to load package entry-point: {e}')

    # entry_points().load() may return a module or an object; we need a module
    if not isinstance(module, ModuleType):
        # If it resolved to an object (e.g., a function), get its module
        if hasattr(module, '__module__'):
            actual_module = sys.modules.get(module.__module__)
            if actual_module:
                return actual_module
        raise FatalError(f'Plugin "{name}": entry-point did not resolve to a module. Ensure the entry-point value points to a module, not a function or class.')

    return module


def load_plugins(plugin_configs: list[PluginConfig], root_dir: Path) -> list[LoadedPlugin]:
    """Load all enabled plugins in config order.

    Args:
        plugin_configs: List of plugin configurations from config.toml.
        root_dir: The root directory of the project.

    Returns:
        List of loaded plugins in config order (skipping disabled ones).

    Raises:
        FatalError: If any enabled plugin cannot be loaded.
    """
    plugins: list[LoadedPlugin] = []

    for pc in plugin_configs:
        if not pc.enabled:
            lg.info(f'Plugin "{pc.name}": skipped (disabled)')
            continue

        lg.info(f'Loading plugin "{pc.name}" (source={pc.source})')
        module = load_plugin(pc, root_dir)
        plugins.append(LoadedPlugin(name=pc.name, module=module, params=pc.params))

    if plugins:
        lg.info(f'Loaded {len(plugins)} plugin(s)')

    return plugins


def run_block_transforms(plugins: list[LoadedPlugin], tree: BlockTree, config) -> BlockTree:
    """Run transform_blocks hooks on all plugins in order.

    Args:
        plugins: List of loaded plugins.
        tree: The block tree to transform.
        config: The Syntagmax Config object.

    Returns:
        The transformed BlockTree.

    Raises:
        FatalError: If a hook raises an exception or returns an invalid type.
    """
    for plugin in plugins:
        if not hasattr(plugin.module, 'transform_blocks'):
            continue

        lg.info(f'Running transform_blocks for plugin "{plugin.name}"')

        try:
            result = plugin.module.transform_blocks(tree, config, plugin.params)
        except FatalError:
            raise
        except Exception as e:
            lg.debug(f'Plugin "{plugin.name}" transform_blocks error:\n{traceback.format_exc()}')
            raise FatalError(f'Plugin "{plugin.name}": transform_blocks raised an exception: {e}')

        if not isinstance(result, BlockTree):
            raise FatalError(f'Plugin "{plugin.name}": transform_blocks must return a BlockTree instance, got {type(result).__name__}')

        tree = result

    return tree


def find_plugin_by_name(plugins: list[LoadedPlugin], name: str) -> LoadedPlugin:
    """Find a loaded plugin by name.

    Args:
        plugins: List of loaded (enabled) plugins.
        name: The plugin name to find.

    Returns:
        The matching LoadedPlugin.

    Raises:
        FatalError: If the plugin is not found among enabled plugins.
    """
    for plugin in plugins:
        if plugin.name == name:
            return plugin

    available = [p.name for p in plugins]
    if available:
        raise FatalError(
            f'Plugin "{name}" not found among enabled plugins. '
            f'Available: {", ".join(available)}. '
            f'Check that the plugin is configured in config.toml and enabled.'
        )
    else:
        raise FatalError(f'Plugin "{name}" not found. No plugins are configured or enabled in config.toml.')


def run_trace_export(plugin: LoadedPlugin, matrix, config) -> None:
    """Run the export_trace hook on a specific plugin.

    Args:
        plugin: The loaded plugin to invoke.
        matrix: The TraceMatrix object to export.
        config: The Syntagmax Config object.

    Raises:
        FatalError: If the plugin does not have an export_trace hook or if it raises.
    """
    if not hasattr(plugin.module, 'export_trace'):
        raise FatalError(f'Plugin "{plugin.name}" does not implement the export_trace hook')

    lg.info(f'Running export_trace for plugin "{plugin.name}"')

    try:
        plugin.module.export_trace(matrix, config, plugin.params)
    except FatalError:
        raise
    except Exception as e:
        lg.debug(f'Plugin "{plugin.name}" export_trace error:\n{traceback.format_exc()}')
        raise FatalError(f'Plugin "{plugin.name}": export_trace raised an exception: {e}')


def run_markdown_transforms(plugins: list[LoadedPlugin], markdown: str, config) -> str:
    """Run transform_markdown hooks on all plugins in order.

    Args:
        plugins: List of loaded plugins.
        markdown: The rendered markdown string to transform.
        config: The Syntagmax Config object.

    Returns:
        The transformed markdown string.

    Raises:
        FatalError: If a hook raises an exception or returns an invalid type.
    """
    for plugin in plugins:
        if not hasattr(plugin.module, 'transform_markdown'):
            continue

        lg.info(f'Running transform_markdown for plugin "{plugin.name}"')

        try:
            result = plugin.module.transform_markdown(markdown, config, plugin.params)
        except FatalError:
            raise
        except Exception as e:
            lg.debug(f'Plugin "{plugin.name}" transform_markdown error:\n{traceback.format_exc()}')
            raise FatalError(f'Plugin "{plugin.name}": transform_markdown raised an exception: {e}')

        if not isinstance(result, str):
            raise FatalError(f'Plugin "{plugin.name}": transform_markdown must return a str instance, got {type(result).__name__}')

        markdown = result

    return markdown


def run_pre_filter(plugin: LoadedPlugin, tree: BlockTree, config) -> BlockTree:
    """Run the filter_block hook on a specific plugin for every block in the tree.

    The hook is called once per block. It may return the block (possibly modified)
    or None to omit the block from the output.

    Args:
        plugin: The loaded plugin to invoke.
        tree: The block tree to filter.
        config: The Syntagmax Config object.

    Returns:
        The filtered BlockTree.

    Raises:
        FatalError: If the plugin lacks filter_block, or if the hook raises
                    an exception or returns an invalid type.
    """
    if not hasattr(plugin.module, 'filter_block'):
        raise FatalError(f'Plugin "{plugin.name}" does not implement the filter_block hook')

    lg.info(f'Running filter_block for plugin "{plugin.name}"')

    for input_block in tree.inputs:
        for file_record in input_block.files:
            new_blocks = []
            for block in file_record.blocks:
                try:
                    result = plugin.module.filter_block(block, file_record, config, plugin.params)
                except FatalError:
                    raise
                except Exception as e:
                    lg.debug(f'Plugin "{plugin.name}" filter_block error:\n{traceback.format_exc()}')
                    raise FatalError(f'Plugin "{plugin.name}": filter_block raised an exception in file "{file_record.path}": {e}')

                if result is None:
                    continue

                if not isinstance(result, Block):
                    raise FatalError(
                        f'Plugin "{plugin.name}": filter_block must return a Block instance or None, got {type(result).__name__} in file "{file_record.path}"'
                    )

                new_blocks.append(result)

            file_record.blocks = new_blocks

    return tree
