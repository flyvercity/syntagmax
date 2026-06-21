# SPDX-License-Identifier: MIT
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.text import TextExtractor
from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.blocks import BlockTree, InputBlock, FileRecord, TextBlock, ArtifactBlock
from syntagmax.publish import build_block_tree, render_block_tree
from syntagmax.params import Params


@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False, output='console')


class TestBlockTreeModel:
    def test_empty_tree(self):
        tree = BlockTree()
        assert tree.inputs == []

    def test_tree_structure(self):
        tree = BlockTree(inputs=[
            InputBlock(name='reqs', files=[
                FileRecord(path='a.md', blocks=[TextBlock(content='hello')])
            ])
        ])
        assert len(tree.inputs) == 1
        assert tree.inputs[0].name == 'reqs'
        assert len(tree.inputs[0].files) == 1
        assert isinstance(tree.inputs[0].files[0].blocks[0], TextBlock)


class TestTextExtractorBlocks:
    def test_interleaved_blocks(self, params, tmp_path):
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text('base = "."\n[[input]]\nname="t"\ndir="."\ndriver="text"\natype="SRC"\n', encoding='utf-8')
        config = Config(params=params, config_filename=cfg_path)

        content = '# Header\n\n[<\nID = SRC-1\n>>>\nBody A\n>]\n\nMiddle.\n\n[<\nID = SRC-2\n>>>\nBody B\n>]\n\nTrailing.\n'
        f = tmp_path / 'test.py'
        f.write_text(content, encoding='utf-8')

        record = InputRecord(name='t', record_base=tmp_path, filepaths=[f], driver='text', default_atype='SRC', marker='SRC')
        extractor = TextExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(f)

        assert len(blocks) == 5
        assert isinstance(blocks[0], TextBlock)
        assert isinstance(blocks[1], ArtifactBlock)
        assert isinstance(blocks[2], TextBlock)
        assert isinstance(blocks[3], ArtifactBlock)
        assert isinstance(blocks[4], TextBlock)
        assert blocks[1].artifact.aid == 'SRC-1'
        assert blocks[3].artifact.aid == 'SRC-2'


class TestRenderBlockTree:
    def test_render_basic(self):
        artifact = MagicMock()
        artifact.aid = 'REQ-1'
        artifact.contents.return_value = 'The system shall do X.'
        artifact.fields = {'id': 'REQ-1', 'contents': 'The system shall do X.', 'status': 'active'}

        tree = BlockTree(inputs=[
            InputBlock(name='reqs', files=[
                FileRecord(path='req.md', blocks=[
                    TextBlock(content='# Intro\n'),
                    ArtifactBlock(artifact=artifact, raw_text='raw'),
                ])
            ])
        ])

        result = render_block_tree(tree)
        assert '## reqs' in result
        assert '# Intro' in result
        assert '### REQ-1' in result
        assert '| status | active |' in result
        assert '| id |' not in result

    def test_render_list_fields_with_non_strings(self):
        artifact = MagicMock()
        artifact.aid = 'SYS-1'
        artifact.contents.return_value = 'Body'
        artifact.fields = {'id': 'SYS-1', 'contents': 'Body', 'tags': [1, 2], 'verified': True}

        tree = BlockTree(inputs=[
            InputBlock(name='sys', files=[
                FileRecord(path='sys.md', blocks=[
                    ArtifactBlock(artifact=artifact, raw_text='raw'),
                ])
            ])
        ])

        result = render_block_tree(tree)
        assert '| tags | 1, 2 |' in result
        assert '| verified | True |' in result


class TestBuildBlockTree:
    def test_lexicographic_order(self, params, tmp_path):
        src_dir = tmp_path / 'src'
        src_dir.mkdir()
        (src_dir / 'b_file.py').write_text('[< ID=SRC-B >>> B >]', encoding='utf-8')
        (src_dir / 'a_file.py').write_text('[< ID=SRC-A >>> A >]', encoding='utf-8')

        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text('base = "."\n[[input]]\nname="src"\ndir="src"\ndriver="text"\natype="SRC"\nfilter="**/*.py"\n', encoding='utf-8')
        cfg = Config(params=params, config_filename=cfg_path)

        tree = build_block_tree(cfg)
        assert len(tree.inputs) == 1
        files = tree.inputs[0].files
        assert len(files) == 2
        assert 'a_file.py' in files[0].path
        assert 'b_file.py' in files[1].path
