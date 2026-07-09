# SPDX-License-Identifier: MIT
import sys
import pytest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from syntagmax.plugin import (
    PluginConfig,
    LoadedPlugin,
    load_plugin,
    load_plugins,
    run_block_transforms,
    run_markdown_transforms,
    run_pre_filter,
)
from syntagmax.blocks import BlockTree, InputBlock, FileRecord, TextBlock
from syntagmax.errors import FatalError


# --- PluginConfig model tests ---


class TestPluginConfig:
    def test_valid_config(self):
        pc = PluginConfig(name='my-plugin', source='local', params={'key': 'value'})
        assert pc.name == 'my-plugin'
        assert pc.source == 'local'
        assert pc.enabled is True
        assert pc.params == {'key': 'value'}

    def test_valid_config_package_source(self):
        pc = PluginConfig(name='pkg-plugin', source='package')
        assert pc.source == 'package'
        assert pc.params == {}

    def test_enabled_false(self):
        pc = PluginConfig(name='disabled', source='local', enabled=False)
        assert pc.enabled is False

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            PluginConfig(source='local')

    def test_missing_source_raises(self):
        with pytest.raises(ValidationError):
            PluginConfig(name='test')

    def test_invalid_source_raises(self):
        with pytest.raises(ValidationError):
            PluginConfig(name='test', source='invalid')

    def test_empty_params_default(self):
        pc = PluginConfig(name='x', source='local')
        assert pc.params == {}

    def test_nested_params(self):
        pc = PluginConfig(name='x', source='local', params={'strip_marker': 'CLASSIFIED', 'level': 3})
        assert pc.params['strip_marker'] == 'CLASSIFIED'
        assert pc.params['level'] == 3


# --- Plugin loader tests ---


class TestLoadLocalPlugin:
    def test_load_single_file(self, tmp_path):
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        plugin_file = plugins_dir / 'my_plugin.py'
        plugin_file.write_text('def transform_markdown(md, config, params):\n    return md + "footer"\n')

        pc = PluginConfig(name='my_plugin', source='local')
        module = load_plugin(pc, tmp_path)

        assert hasattr(module, 'transform_markdown')
        assert module.transform_markdown('hello', None, {}) == 'hellofooter'

        # Cleanup sys.modules
        sys.modules.pop('syntagmax.plugins.local.my_plugin', None)

    def test_load_directory_plugin(self, tmp_path):
        plugins_dir = tmp_path / 'plugins'
        pkg_dir = plugins_dir / 'dir_plugin'
        pkg_dir.mkdir(parents=True)

        helpers_file = pkg_dir / 'helpers.py'
        helpers_file.write_text('VALUE = 1\n', encoding='utf-8')

        init_file = pkg_dir / '__init__.py'
        init_file.write_text(
            'from .helpers import VALUE\n\n'
            'def transform_blocks(tree, config, params):\n'
            '    return tree\n',
            encoding='utf-8',
        )

        pc = PluginConfig(name='dir_plugin', source='local')
        module = load_plugin(pc, tmp_path)

        assert hasattr(module, 'transform_blocks')

        # Cleanup sys.modules
        sys.modules.pop('syntagmax.plugins.local.dir_plugin', None)

    def test_missing_local_plugin_raises(self, tmp_path):
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()

        pc = PluginConfig(name='nonexistent', source='local')
        with pytest.raises(FatalError, match='local plugin not found'):
            load_plugin(pc, tmp_path)

    def test_local_plugin_with_syntax_error(self, tmp_path):
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        plugin_file = plugins_dir / 'bad_plugin.py'
        plugin_file.write_text('def broken(\n')

        pc = PluginConfig(name='bad_plugin', source='local')
        with pytest.raises(FatalError, match='failed to load'):
            load_plugin(pc, tmp_path)

    def test_local_plugin_registered_in_sys_modules(self, tmp_path):
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        plugin_file = plugins_dir / 'registered.py'
        plugin_file.write_text('VALUE = 42\n')

        pc = PluginConfig(name='registered', source='local')
        load_plugin(pc, tmp_path)

        assert 'syntagmax.plugins.local.registered' in sys.modules

        # Cleanup
        sys.modules.pop('syntagmax.plugins.local.registered', None)

    def test_single_file_takes_priority_over_directory(self, tmp_path):
        """If both name.py and name/__init__.py exist, the single file wins."""
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()

        # Single file
        single_file = plugins_dir / 'priority.py'
        single_file.write_text('SOURCE = "file"\n')

        # Directory
        pkg_dir = plugins_dir / 'priority'
        pkg_dir.mkdir()
        (pkg_dir / '__init__.py').write_text('SOURCE = "dir"\n')

        pc = PluginConfig(name='priority', source='local')
        module = load_plugin(pc, tmp_path)

        assert module.SOURCE == 'file'

        # Cleanup
        sys.modules.pop('syntagmax.plugins.local.priority', None)


class TestLoadPackagePlugin:
    def test_load_package_plugin(self):
        mock_module = ModuleType('syntagmax_test_pkg')
        mock_module.transform_markdown = lambda md, config, params: md

        mock_ep = MagicMock()
        mock_ep.load.return_value = mock_module

        with patch('syntagmax.plugin.importlib.metadata.entry_points', return_value=[mock_ep]):
            pc = PluginConfig(name='test-pkg', source='package')
            module = load_plugin(pc, Path('.'))

        assert module is mock_module

    def test_missing_package_plugin_raises(self):
        with patch('syntagmax.plugin.importlib.metadata.entry_points', return_value=[]):
            pc = PluginConfig(name='missing-pkg', source='package')
            with pytest.raises(FatalError, match='no package entry-point found'):
                load_plugin(pc, Path('.'))

    def test_package_plugin_load_failure(self):
        mock_ep = MagicMock()
        mock_ep.load.side_effect = ImportError('module not found')

        with patch('syntagmax.plugin.importlib.metadata.entry_points', return_value=[mock_ep]):
            pc = PluginConfig(name='broken-pkg', source='package')
            with pytest.raises(FatalError, match='failed to load package entry-point'):
                load_plugin(pc, Path('.'))


class TestLoadPlugins:
    def test_load_multiple_in_order(self, tmp_path):
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        (plugins_dir / 'first.py').write_text('ORDER = 1\n')
        (plugins_dir / 'second.py').write_text('ORDER = 2\n')

        configs = [
            PluginConfig(name='first', source='local', params={'a': 1}),
            PluginConfig(name='second', source='local', params={'b': 2}),
        ]
        loaded = load_plugins(configs, tmp_path)

        assert len(loaded) == 2
        assert loaded[0].name == 'first'
        assert loaded[0].module.ORDER == 1
        assert loaded[0].params == {'a': 1}
        assert loaded[1].name == 'second'
        assert loaded[1].module.ORDER == 2
        assert loaded[1].params == {'b': 2}

        # Cleanup
        sys.modules.pop('syntagmax.plugins.local.first', None)
        sys.modules.pop('syntagmax.plugins.local.second', None)

    def test_disabled_plugins_are_skipped(self, tmp_path):
        plugins_dir = tmp_path / 'plugins'
        plugins_dir.mkdir()
        (plugins_dir / 'active.py').write_text('ACTIVE = True\n')

        configs = [
            PluginConfig(name='active', source='local'),
            PluginConfig(name='disabled', source='local', enabled=False),
        ]
        loaded = load_plugins(configs, tmp_path)

        assert len(loaded) == 1
        assert loaded[0].name == 'active'

        # Cleanup
        sys.modules.pop('syntagmax.plugins.local.active', None)

    def test_empty_config_returns_empty(self, tmp_path):
        loaded = load_plugins([], tmp_path)
        assert loaded == []


# --- Execution engine tests ---


def _make_tree_with_text(content: str) -> BlockTree:
    tree = BlockTree()
    tree.inputs.append(
        InputBlock(name='test', files=[FileRecord(path='test.md', blocks=[TextBlock(content=content)])])
    )
    return tree


def _make_plugin_module(name: str, **funcs) -> LoadedPlugin:
    mod = ModuleType(name)
    for func_name, func in funcs.items():
        setattr(mod, func_name, func)
    return LoadedPlugin(name=name, module=mod, params={})


class TestRunBlockTransforms:
    def test_single_plugin_transforms_tree(self):
        def transform_blocks(tree, config, params):
            tree.inputs[0].files[0].blocks[0].content = 'MODIFIED'
            return tree

        plugin = _make_plugin_module('test', transform_blocks=transform_blocks)
        tree = _make_tree_with_text('original')

        result = run_block_transforms([plugin], tree, None)
        assert result.inputs[0].files[0].blocks[0].content == 'MODIFIED'

    def test_chaining_order(self):
        def transform_a(tree, config, params):
            tree.inputs[0].files[0].blocks[0].content += '_A'
            return tree

        def transform_b(tree, config, params):
            tree.inputs[0].files[0].blocks[0].content += '_B'
            return tree

        plugin_a = _make_plugin_module('a', transform_blocks=transform_a)
        plugin_b = _make_plugin_module('b', transform_blocks=transform_b)
        tree = _make_tree_with_text('start')

        result = run_block_transforms([plugin_a, plugin_b], tree, None)
        assert result.inputs[0].files[0].blocks[0].content == 'start_A_B'

    def test_plugin_without_hook_is_skipped(self):
        plugin = _make_plugin_module('no_hook')
        tree = _make_tree_with_text('unchanged')

        result = run_block_transforms([plugin], tree, None)
        assert result.inputs[0].files[0].blocks[0].content == 'unchanged'

    def test_exception_raises_fatal_error(self):
        def bad_transform(tree, config, params):
            raise ValueError('boom')

        plugin = _make_plugin_module('bad', transform_blocks=bad_transform)
        tree = _make_tree_with_text('x')

        with pytest.raises(FatalError, match='bad.*transform_blocks raised an exception.*boom'):
            run_block_transforms([plugin], tree, None)

    def test_returning_none_raises_fatal_error(self):
        def none_transform(tree, config, params):
            return None

        plugin = _make_plugin_module('none_ret', transform_blocks=none_transform)
        tree = _make_tree_with_text('x')

        with pytest.raises(FatalError, match='none_ret.*must return a BlockTree'):
            run_block_transforms([plugin], tree, None)

    def test_returning_wrong_type_raises_fatal_error(self):
        def wrong_type(tree, config, params):
            return 'not a tree'

        plugin = _make_plugin_module('wrong', transform_blocks=wrong_type)
        tree = _make_tree_with_text('x')

        with pytest.raises(FatalError, match='wrong.*must return a BlockTree'):
            run_block_transforms([plugin], tree, None)

    def test_params_are_passed(self):
        received_params = {}

        def capture_params(tree, config, params):
            received_params.update(params)
            return tree

        plugin = LoadedPlugin(name='p', module=ModuleType('p'), params={'key': 'val'})
        plugin.module.transform_blocks = capture_params

        tree = _make_tree_with_text('x')
        run_block_transforms([plugin], tree, None)

        assert received_params == {'key': 'val'}


class TestRunMarkdownTransforms:
    def test_single_plugin_transforms_markdown(self):
        def transform_markdown(md, config, params):
            return md + '\n---\nFooter'

        plugin = _make_plugin_module('footer', transform_markdown=transform_markdown)

        result = run_markdown_transforms([plugin], '# Title\n', None)
        assert result == '# Title\n\n---\nFooter'

    def test_chaining_order(self):
        def transform_a(md, config, params):
            return md + '_A'

        def transform_b(md, config, params):
            return md + '_B'

        plugin_a = _make_plugin_module('a', transform_markdown=transform_a)
        plugin_b = _make_plugin_module('b', transform_markdown=transform_b)

        result = run_markdown_transforms([plugin_a, plugin_b], 'start', None)
        assert result == 'start_A_B'

    def test_plugin_without_hook_is_skipped(self):
        plugin = _make_plugin_module('no_hook')
        result = run_markdown_transforms([plugin], 'unchanged', None)
        assert result == 'unchanged'

    def test_exception_raises_fatal_error(self):
        def bad_transform(md, config, params):
            raise RuntimeError('crash')

        plugin = _make_plugin_module('bad', transform_markdown=bad_transform)

        with pytest.raises(FatalError, match='bad.*transform_markdown raised an exception.*crash'):
            run_markdown_transforms([plugin], 'x', None)

    def test_returning_none_raises_fatal_error(self):
        def none_transform(md, config, params):
            return None

        plugin = _make_plugin_module('none_ret', transform_markdown=none_transform)

        with pytest.raises(FatalError, match='none_ret.*must return a str'):
            run_markdown_transforms([plugin], 'x', None)

    def test_returning_wrong_type_raises_fatal_error(self):
        def wrong_type(md, config, params):
            return 123

        plugin = _make_plugin_module('wrong', transform_markdown=wrong_type)

        with pytest.raises(FatalError, match='wrong.*must return a str'):
            run_markdown_transforms([plugin], 'x', None)

    def test_params_are_passed(self):
        received_params = {}

        def capture_params(md, config, params):
            received_params.update(params)
            return md

        plugin = LoadedPlugin(name='p', module=ModuleType('p'), params={'footer': '---'})
        plugin.module.transform_markdown = capture_params

        run_markdown_transforms([plugin], 'text', None)

        assert received_params == {'footer': '---'}

    def test_both_hooks_on_same_plugin(self):
        def transform_blocks(tree, config, params):
            tree.inputs[0].files[0].blocks[0].content = 'BLOCK_MODIFIED'
            return tree

        def transform_markdown(md, config, params):
            return md + '_MD_MODIFIED'

        plugin = _make_plugin_module('both', transform_blocks=transform_blocks, transform_markdown=transform_markdown)
        tree = _make_tree_with_text('original')

        tree = run_block_transforms([plugin], tree, None)
        assert tree.inputs[0].files[0].blocks[0].content == 'BLOCK_MODIFIED'

        md = run_markdown_transforms([plugin], 'rendered', None)
        assert md == 'rendered_MD_MODIFIED'



class TestRunPreFilter:
    def test_filter_block_called_for_each_block(self):
        call_log = []

        def filter_block(block, file_record, config, params):
            call_log.append(block.content)
            return block

        plugin = _make_plugin_module('test', filter_block=filter_block)
        tree = BlockTree(inputs=[
            InputBlock(name='inp', files=[
                FileRecord(path='a.md', blocks=[TextBlock(content='one'), TextBlock(content='two')]),
                FileRecord(path='b.md', blocks=[TextBlock(content='three')]),
            ])
        ])

        run_pre_filter(plugin, tree, None)
        assert call_log == ['one', 'two', 'three']

    def test_returned_block_replaces_original(self):
        def filter_block(block, file_record, config, params):
            return TextBlock(content=block.content.upper())

        plugin = _make_plugin_module('upper', filter_block=filter_block)
        tree = _make_tree_with_text('hello')

        result = run_pre_filter(plugin, tree, None)
        assert result.inputs[0].files[0].blocks[0].content == 'HELLO'

    def test_file_record_passed_correctly(self):
        received_paths = []

        def filter_block(block, file_record, config, params):
            received_paths.append(file_record.path)
            return block

        plugin = _make_plugin_module('ctx', filter_block=filter_block)
        tree = BlockTree(inputs=[
            InputBlock(name='inp', files=[
                FileRecord(path='src/req.md', blocks=[TextBlock(content='x')]),
                FileRecord(path='src/sys.md', blocks=[TextBlock(content='y')]),
            ])
        ])

        run_pre_filter(plugin, tree, None)
        assert received_paths == ['src/req.md', 'src/sys.md']

    def test_returning_none_removes_block(self):
        def filter_block(block, file_record, config, params):
            if block.content == 'remove_me':
                return None
            return block

        plugin = _make_plugin_module('strip', filter_block=filter_block)
        tree = BlockTree(inputs=[
            InputBlock(name='inp', files=[
                FileRecord(path='a.md', blocks=[
                    TextBlock(content='keep'),
                    TextBlock(content='remove_me'),
                    TextBlock(content='also_keep'),
                ])
            ])
        ])

        result = run_pre_filter(plugin, tree, None)
        blocks = result.inputs[0].files[0].blocks
        assert len(blocks) == 2
        assert blocks[0].content == 'keep'
        assert blocks[1].content == 'also_keep'

    def test_returning_non_block_raises_fatal_error(self):
        def filter_block(block, file_record, config, params):
            return 'not a block'

        plugin = _make_plugin_module('bad', filter_block=filter_block)
        tree = _make_tree_with_text('x')

        with pytest.raises(FatalError, match='bad.*filter_block must return a Block instance or None.*got str'):
            run_pre_filter(plugin, tree, None)

    def test_exception_raises_fatal_error_with_file_path(self):
        def filter_block(block, file_record, config, params):
            raise ValueError('boom')

        plugin = _make_plugin_module('explode', filter_block=filter_block)
        tree = BlockTree(inputs=[
            InputBlock(name='inp', files=[
                FileRecord(path='reqs/SYS-001.md', blocks=[TextBlock(content='x')])
            ])
        ])

        with pytest.raises(FatalError, match='explode.*filter_block raised.*reqs/SYS-001.md.*boom'):
            run_pre_filter(plugin, tree, None)

    def test_missing_filter_block_raises_fatal_error(self):
        plugin = _make_plugin_module('no_hook')
        tree = _make_tree_with_text('x')

        with pytest.raises(FatalError, match='no_hook.*does not implement the filter_block hook'):
            run_pre_filter(plugin, tree, None)

    def test_params_are_passed(self):
        received_params = {}

        def filter_block(block, file_record, config, params):
            received_params.update(params)
            return block

        plugin = LoadedPlugin(name='p', module=ModuleType('p'), params={'marker': 'DRAFT'})
        plugin.module.filter_block = filter_block

        tree = _make_tree_with_text('x')
        run_pre_filter(plugin, tree, None)

        assert received_params == {'marker': 'DRAFT'}
