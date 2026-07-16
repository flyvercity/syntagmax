# SPDX-License-Identifier: MIT
# Tests for Obsidian Attachment Folder Path Integration

import json
import pytest
from pathlib import Path

from syntagmax.config import Config
from syntagmax.obsidian_settings import read_obsidian_attachment_path
from syntagmax.publish_context import RenderContext, resolve_image_to_manifest
from syntagmax.params import Params
from syntagmax.publish import render_block_tree, build_block_tree


@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False, output='console')


class TestObsidianDriverConfigFields:
    """Task 1: Verify new fields parse correctly."""

    def test_integration_and_root_parsed(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n'
            '[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n'
            '[drivers.obsidian]\nintegration = true\nroot = ".obsidian-custom"\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / '..' / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)

        config = Config(params=params, config_filename=cfg_path)
        assert config.obsidian_driver_config.integration is True
        assert config.obsidian_driver_config.root == '.obsidian-custom'

    def test_defaults_when_absent(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / '..' / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)

        config = Config(params=params, config_filename=cfg_path)
        assert config.obsidian_driver_config.integration is False
        assert config.obsidian_driver_config.root is None


class TestObsidianSettingsReader:
    """Task 2: Unit tests for read_obsidian_attachment_path."""

    def test_successful_read(self, tmp_path):
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()
        app_json = obsidian_dir / 'app.json'
        app_json.write_text(json.dumps({'attachmentFolderPath': 'attachments/pics'}), encoding='utf-8')

        result = read_obsidian_attachment_path(tmp_path)
        assert result == 'attachments/pics'

    def test_missing_app_json(self, tmp_path, caplog):
        result = read_obsidian_attachment_path(tmp_path)
        assert result is None
        assert 'not found' in caplog.text

    def test_malformed_json(self, tmp_path, caplog):
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()
        app_json = obsidian_dir / 'app.json'
        app_json.write_text('{ invalid json !!!', encoding='utf-8')

        result = read_obsidian_attachment_path(tmp_path)
        assert result is None
        assert 'malformed JSON' in caplog.text

    def test_missing_key(self, tmp_path, caplog):
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()
        app_json = obsidian_dir / 'app.json'
        app_json.write_text(json.dumps({'otherSetting': True}), encoding='utf-8')

        result = read_obsidian_attachment_path(tmp_path)
        assert result is None
        assert 'attachmentFolderPath not set' in caplog.text

    def test_custom_root_override(self, tmp_path):
        custom_dir = tmp_path / 'my-obsidian'
        custom_dir.mkdir()
        app_json = custom_dir / 'app.json'
        app_json.write_text(json.dumps({'attachmentFolderPath': 'imgs'}), encoding='utf-8')

        result = read_obsidian_attachment_path(tmp_path, root_override='my-obsidian')
        assert result == 'imgs'


class TestRenderContextLazyLoading:
    """Task 3: Verify lazy loading behaviour."""

    def test_no_io_when_integration_disabled(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n',
            encoding='utf-8',
        )
        req_dir = tmp_path / '..' / 'REQ'
        req_dir.mkdir(parents=True, exist_ok=True)

        config = Config(params=params, config_filename=cfg_path)
        context = RenderContext(config=config)

        # Should return None without reading any files
        assert context.obsidian_attachment_path is None

    def test_lazy_load_on_access(self, params, tmp_path):
        base_dir = tmp_path / 'project'
        base_dir.mkdir()
        syntagmax_dir = base_dir / '.syntagmax'
        syntagmax_dir.mkdir()
        req_dir = base_dir / 'REQ'
        req_dir.mkdir()

        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': 'attachments'}), encoding='utf-8')

        cfg_path = syntagmax_dir / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nintegration = true\n',
            encoding='utf-8',
        )

        config = Config(params=params, config_filename=cfg_path)
        context = RenderContext(config=config)

        assert context.obsidian_attachment_path == 'attachments'
        # Subsequent access returns cached value
        assert context.obsidian_attachment_path == 'attachments'


class TestImageResolutionWithAttachmentFolder:
    """Task 4: Image resolution tests."""

    def _make_project(self, tmp_path, attachment_path='attachments/pics', integration=True):
        """Helper to create a project with Obsidian attachment integration."""
        base_dir = tmp_path / 'project'
        base_dir.mkdir()
        syntagmax_dir = base_dir / '.syntagmax'
        syntagmax_dir.mkdir()
        req_dir = base_dir / 'REQ'
        req_dir.mkdir()
        (req_dir / 'REQ-001.md').write_text('---\nid: REQ-001\ncontents: See ![[diagram.png]]\n---\n', encoding='utf-8')

        # Create attachment folder with image
        attach_dir = base_dir / Path(attachment_path)
        attach_dir.mkdir(parents=True, exist_ok=True)
        img = attach_dir / 'diagram.png'
        img.write_bytes(b'\x89PNG\r\n')

        # Create .obsidian/app.json
        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': attachment_path}), encoding='utf-8')

        integration_line = f'integration = {"true" if integration else "false"}'
        cfg_path = syntagmax_dir / 'config.toml'
        cfg_path.write_text(
            f'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\n{integration_line}\n',
            encoding='utf-8',
        )

        return cfg_path, base_dir

    def test_attachment_folder_resolves_image(self, params, tmp_path):
        cfg_path, _ = self._make_project(tmp_path)
        config = Config(params=params, config_filename=cfg_path)
        context = RenderContext(config=config)
        context.source_file_path = 'REQ/REQ-001.md'

        result = resolve_image_to_manifest('diagram.png', context, is_obsidian=True)
        assert result is not None
        assert 'diagram.png' in result
        assert result.startswith('images/')

    def test_fallback_skipped_when_integration_disabled(self, params, tmp_path):
        cfg_path, _ = self._make_project(tmp_path, integration=False)
        config = Config(params=params, config_filename=cfg_path)
        context = RenderContext(config=config)
        context.source_file_path = 'REQ/REQ-001.md'

        # Image is ONLY in attachment folder, not in input records
        result = resolve_image_to_manifest('diagram.png', context, is_obsidian=True)
        assert result is None

    def test_note_relative_attachment_path(self, params, tmp_path):
        """Note-relative path ./attachments resolves relative to the source note."""
        base_dir = tmp_path / 'project'
        base_dir.mkdir()
        syntagmax_dir = base_dir / '.syntagmax'
        syntagmax_dir.mkdir()
        req_dir = base_dir / 'REQ'
        req_dir.mkdir()
        (req_dir / 'REQ-001.md').write_text('---\nid: REQ-001\n---\n', encoding='utf-8')

        # Create note-relative attachment folder
        attach_dir = req_dir / 'attachments'
        attach_dir.mkdir()
        img = attach_dir / 'photo.png'
        img.write_bytes(b'\x89PNG\r\n')

        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': './attachments'}), encoding='utf-8')

        cfg_path = syntagmax_dir / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nintegration = true\n',
            encoding='utf-8',
        )

        config = Config(params=params, config_filename=cfg_path)
        context = RenderContext(config=config)
        context.source_file_path = 'REQ/REQ-001.md'

        result = resolve_image_to_manifest('photo.png', context, is_obsidian=True)
        assert result is not None
        assert 'photo.png' in result

    def test_vault_wide_scan_still_works_as_fallback(self, params, tmp_path):
        """If image is in an input record directory (not attachment folder), it still resolves."""
        base_dir = tmp_path / 'project'
        base_dir.mkdir()
        syntagmax_dir = base_dir / '.syntagmax'
        syntagmax_dir.mkdir()
        sys_dir = base_dir / 'SYS'
        sys_dir.mkdir()

        # Image is directly in the input record directory
        img = sys_dir / 'arch.png'
        img.write_bytes(b'\x89PNG\r\n')

        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': 'attachments'}), encoding='utf-8')

        # Create empty attachments folder (image NOT there)
        (base_dir / 'attachments').mkdir()

        cfg_path = syntagmax_dir / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="sys"\ndir="SYS"\ndriver="obsidian"\natype="SYS"\nfilter="**/*"\n\n[drivers.obsidian]\nintegration = true\n',
            encoding='utf-8',
        )

        config = Config(params=params, config_filename=cfg_path)
        context = RenderContext(config=config)
        context.source_file_path = 'SYS/SYS-001.md'

        result = resolve_image_to_manifest('arch.png', context, is_obsidian=True)
        assert result is not None
        assert 'arch.png' in result

    def test_attachment_folder_takes_priority(self, params, tmp_path):
        """If image exists in both attachment folder and input records, attachment folder wins."""
        base_dir = tmp_path / 'project'
        base_dir.mkdir()
        syntagmax_dir = base_dir / '.syntagmax'
        syntagmax_dir.mkdir()
        sys_dir = base_dir / 'SYS'
        sys_dir.mkdir()

        # Image in input record
        img_in_record = sys_dir / 'shared.png'
        img_in_record.write_bytes(b'\x89PNG record version')

        # Image in attachment folder
        attach_dir = base_dir / 'attachments'
        attach_dir.mkdir()
        img_in_attach = attach_dir / 'shared.png'
        img_in_attach.write_bytes(b'\x89PNG attach version')

        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': 'attachments'}), encoding='utf-8')

        cfg_path = syntagmax_dir / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="sys"\ndir="SYS"\ndriver="obsidian"\natype="SYS"\nfilter="**/*"\n\n[drivers.obsidian]\nintegration = true\n',
            encoding='utf-8',
        )

        config = Config(params=params, config_filename=cfg_path)
        context = RenderContext(config=config)
        context.source_file_path = 'SYS/SYS-001.md'

        result = resolve_image_to_manifest('shared.png', context, is_obsidian=True)
        assert result is not None
        # Should resolve from attachments folder (checked first)
        assert 'attachments' in result


class TestEndToEndPublishWithAttachments:
    """Task 5: Full pipeline end-to-end test."""

    def test_publish_rewrites_obsidian_image_via_attachment_folder(self, params, tmp_path):
        """Full flow: config → extract → render → verify manifest and output."""
        base_dir = tmp_path / 'project'
        base_dir.mkdir()
        syntagmax_dir = base_dir / '.syntagmax'
        syntagmax_dir.mkdir()

        # Create requirement with image reference
        req_dir = base_dir / 'REQ'
        req_dir.mkdir()
        (req_dir / 'REQ-001.md').write_text(
            '---\nid: REQ-001\ncontents: Requirements overview\nstatus: active\n---\n\nSee the architecture diagram:\n\n![[arch-overview.png]]\n',
            encoding='utf-8',
        )

        # Create attachment folder with the image
        attach_dir = base_dir / 'attachments'
        attach_dir.mkdir()
        (attach_dir / 'arch-overview.png').write_bytes(b'\x89PNG\r\n\x1a\n')

        # Create .obsidian/app.json
        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': 'attachments'}), encoding='utf-8')

        cfg_path = syntagmax_dir / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nintegration = true\n',
            encoding='utf-8',
        )

        config = Config(params=params, config_filename=cfg_path)
        tree, _errors = build_block_tree(config)

        result, manifest = render_block_tree(tree, config=config, multi_record=False)

        # Image reference should be rewritten
        assert '![](images/' in result
        assert '![[arch-overview.png]]' not in result

        # Manifest should contain the attachment image
        assert len(manifest) == 1
        entries = manifest.entries
        source_paths = list(entries.keys())
        assert any('arch-overview.png' in str(p) for p in source_paths)

    def test_publish_with_note_relative_attachment_path(self, params, tmp_path):
        """End-to-end with note-relative attachment configuration."""
        base_dir = tmp_path / 'project'
        base_dir.mkdir()
        syntagmax_dir = base_dir / '.syntagmax'
        syntagmax_dir.mkdir()

        req_dir = base_dir / 'REQ'
        req_dir.mkdir()
        (req_dir / 'REQ-001.md').write_text(
            '---\nid: REQ-001\ncontents: Detail\nstatus: draft\n---\n\n![[local-diagram.png]]\n',
            encoding='utf-8',
        )

        # Note-relative: ./assets means REQ/assets/
        assets_dir = req_dir / 'assets'
        assets_dir.mkdir()
        (assets_dir / 'local-diagram.png').write_bytes(b'\x89PNG\r\n\x1a\n')

        obsidian_dir = base_dir / '.obsidian'
        obsidian_dir.mkdir()
        (obsidian_dir / 'app.json').write_text(json.dumps({'attachmentFolderPath': './assets'}), encoding='utf-8')

        cfg_path = syntagmax_dir / 'config.toml'
        cfg_path.write_text(
            'base = ".."\n[[input]]\nname="reqs"\ndir="REQ"\ndriver="obsidian"\natype="REQ"\n\n[drivers.obsidian]\nintegration = true\n',
            encoding='utf-8',
        )

        config = Config(params=params, config_filename=cfg_path)
        tree, _errors = build_block_tree(config)

        result, manifest = render_block_tree(tree, config=config, multi_record=False)

        assert '![](images/' in result
        assert '![[local-diagram.png]]' not in result
        assert len(manifest) == 1
