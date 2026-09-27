# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: Tests for the driver-agnostic write seam (edit/create/delete), obsidian driver.

from pathlib import Path

import pytest

from syntagmax.artifact import Artifact
from syntagmax.config import Config, InputRecord
from syntagmax.errors import UnsupportedOperation
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.extractors.simple_markdown import SimpleMarkdownExtractor
from syntagmax.params import Params


@pytest.fixture
def params():
    return Params(
        verbose=False,
        render_tree=False,
        ai=False,
        cwd='.',
        no_git=True,
        allow_dirty_worktree=True,
        suppress_tracing=True,
    )


def _make_config(params, tmp_path) -> Config:
    cfg_content = 'base = "."\n[[input]]\nname = "requirements"\ndir = "REQ"\ndriver = "obsidian"\natype = "REQ"\n'
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(cfg_content, encoding='utf-8')
    return Config(params=params, config_filename=cfg_path)


def _make_extractor(config, tmp_path) -> ObsidianExtractor:
    record = InputRecord(
        name='requirements',
        dir='REQ',
        record_base=tmp_path,
        filepaths=[],
        driver='obsidian',
        default_atype='REQ',
        marker='REQ',
    )
    return ObsidianExtractor(config, record, config.metamodel)


def _write_req(tmp_path, filename: str, content: str) -> Path:
    req_dir = tmp_path / 'REQ'
    req_dir.mkdir(exist_ok=True)
    f = req_dir / filename
    f.write_text(content, encoding='utf-8')
    return f


def _extract(extractor: ObsidianExtractor, path: Path) -> dict[str, Artifact]:
    artifacts, _errors = extractor.extract_from_file(path)
    return {a.aid: a for a in artifacts}


def _get(extractor: ObsidianExtractor, path: Path, aid: str) -> Artifact:
    arts = _extract(extractor, path)
    assert aid in arts, f'{aid} not found in {list(arts)}'
    return arts[aid]


REQ_ONE = '[REQ]\nBody text\n[id] REQ-001\n```yaml\nattrs:\n  id: REQ-001\n  title: Sample\n  status: draft\n```\n'


# ==============================================================================
# edit_artifact
# ==============================================================================


class TestEditArtifact:
    def test_edit_field_updates_value(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)
        f = _write_req(tmp_path, 'REQ-001.md', REQ_ONE)

        art = _get(extractor, f, 'REQ-001')
        extractor.edit_artifact(art, fields={'status': 'active'})

        updated = _get(extractor, f, 'REQ-001')
        assert updated.fields.get('status') == 'active'

    def test_edit_field_to_none_removes_key(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)
        f = _write_req(tmp_path, 'REQ-001.md', REQ_ONE)

        art = _get(extractor, f, 'REQ-001')
        extractor.edit_artifact(art, fields={'status': None})

        content = f.read_text(encoding='utf-8')
        assert 'status' not in content
        updated = _get(extractor, f, 'REQ-001')
        assert 'status' not in updated.fields
        # Other fields preserved.
        assert updated.fields.get('title') == 'Sample'

    def test_edit_body_replaces_contents(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)
        f = _write_req(tmp_path, 'REQ-001.md', REQ_ONE)

        art = _get(extractor, f, 'REQ-001')
        extractor.edit_artifact(art, body='Completely new body')

        updated = _get(extractor, f, 'REQ-001')
        assert 'Completely new body' in (updated.fields.get('contents') or '')
        assert 'Body text' not in (updated.fields.get('contents') or '')
        # YAML attrs preserved.
        assert updated.fields.get('title') == 'Sample'


# ==============================================================================
# create_artifact
# ==============================================================================


class TestCreateArtifact:
    def test_create_with_explicit_aid_and_parent_dirs(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)

        created = extractor.create_artifact(
            target_file='REQ/nested/deep/NEW-001.md',
            atype='REQ',
            aid='NEW-001',
            fields={'title': 'Created'},
            body='New artifact body',
        )
        assert created.aid == 'NEW-001'

        target = tmp_path / 'REQ' / 'nested' / 'deep' / 'NEW-001.md'
        assert target.exists()

        re_extracted = _get(extractor, target, 'NEW-001')
        assert re_extracted.fields.get('title') == 'Created'
        assert 'New artifact body' in (re_extracted.fields.get('contents') or '')

    def test_create_requires_non_none_aid(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)

        with pytest.raises(ValueError):
            extractor.create_artifact(
                target_file='REQ/NEW.md',
                atype='REQ',
                aid=None,  # type: ignore[arg-type]
                fields={},
                body='x',
            )

    def test_create_traversal_raises_value_error(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)

        with pytest.raises(ValueError):
            extractor.create_artifact(
                target_file='../../evil.md',
                atype='REQ',
                aid='EVIL-001',
                fields={},
                body='malicious',
            )


# ==============================================================================
# delete_artifact
# ==============================================================================


class TestDeleteArtifact:
    def test_delete_one_of_several_keeps_file(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)
        content = (
            '[REQ]\nFirst\n[id] REQ-001\n[/REQ]\n\n'
            '[REQ]\nSecond\n[id] REQ-002\n[/REQ]\n'
        )
        f = _write_req(tmp_path, 'multi.md', content)

        art = _get(extractor, f, 'REQ-001')
        extractor.delete_artifact(art)

        assert f.exists()
        remaining = _extract(extractor, f)
        assert 'REQ-001' not in remaining
        assert 'REQ-002' in remaining

    def test_delete_sole_artifact_removes_file(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)
        f = _write_req(tmp_path, 'REQ-001.md', REQ_ONE)

        art = _get(extractor, f, 'REQ-001')
        extractor.delete_artifact(art)

        assert not f.exists()


# ==============================================================================
# Capabilities & unsupported drivers
# ==============================================================================


class TestCapabilities:
    def test_obsidian_write_capabilities(self):
        assert ObsidianExtractor.WRITE_CAPABILITIES == {'edit', 'create', 'delete'}

    def test_non_obsidian_driver_edit_raises(self, params, tmp_path):
        cfg_content = 'base = "."\n[[input]]\nname = "reqs"\ndir = "."\ndriver = "simple-markdown"\natype = "REQ"\n'
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(cfg_content, encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)
        record = InputRecord(
            name='reqs',
            dir='.',
            record_base=tmp_path,
            filepaths=[],
            driver='simple-markdown',
            default_atype='REQ',
            marker='REQ',
        )
        extractor = SimpleMarkdownExtractor(config, record, config.metamodel)

        assert extractor.WRITE_CAPABILITIES == set()
        art = Artifact(config)
        with pytest.raises(UnsupportedOperation):
            extractor.edit_artifact(art, fields={'status': 'active'})
        with pytest.raises(UnsupportedOperation):
            extractor.create_artifact(target_file='x.md', atype='REQ', aid='REQ-1', fields={}, body='')
        with pytest.raises(UnsupportedOperation):
            extractor.delete_artifact(art)


# ==============================================================================
# Atomicity
# ==============================================================================


class TestAtomicity:
    def test_no_leftover_temp_files_after_edit(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)
        f = _write_req(tmp_path, 'REQ-001.md', REQ_ONE)

        art = _get(extractor, f, 'REQ-001')
        extractor.edit_artifact(art, fields={'status': 'active'}, body='fresh body')

        leftovers = list((tmp_path / 'REQ').glob('*.tmp'))
        assert leftovers == []

    def test_no_leftover_temp_files_after_create(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)

        extractor.create_artifact(
            target_file='REQ/NEW-001.md',
            atype='REQ',
            aid='NEW-001',
            fields={'title': 'X'},
            body='body',
        )
        leftovers = list((tmp_path / 'REQ').glob('*.tmp'))
        assert leftovers == []


# ==============================================================================
# Windows / round-trip: os.replace over an existing file, newline correctness
# ==============================================================================


class TestRoundTripWindows:
    def test_replace_over_existing_file_crlf(self, params, tmp_path):
        config = _make_config(params, tmp_path)
        extractor = _make_extractor(config, tmp_path)
        crlf_content = REQ_ONE.replace('\n', '\r\n')
        req_dir = tmp_path / 'REQ'
        req_dir.mkdir(exist_ok=True)
        f = req_dir / 'REQ-001.md'
        f.write_bytes(crlf_content.encode('utf-8'))

        art = _get(extractor, f, 'REQ-001')
        extractor.edit_artifact(art, fields={'status': 'active'})

        # os.replace succeeded over the existing file.
        assert f.exists()
        raw = f.read_bytes()
        # CRLF newlines preserved (no bare LF introduced).
        assert b'\r\n' in raw
        assert raw.replace(b'\r\n', b'').find(b'\n') == -1

        updated = _get(extractor, f, 'REQ-001')
        assert updated.fields.get('status') == 'active'
