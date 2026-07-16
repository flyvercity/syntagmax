# SPDX-License-Identifier: MIT
import pytest
import textwrap

from syntagmax.config import Config, InputRecord, ExcludeElementConfig
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.blocks import HeadingBlock, TextBlock, ArtifactBlock
from syntagmax.params import Params
from syntagmax.publish import build_block_tree, render_block_tree


@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False, output='console')


@pytest.fixture
def config_file(tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        """
base = "."
[[input]]
name = "test"
dir = "."
driver = "obsidian"
atype = "requirement"
""",
        encoding='utf-8',
    )
    return cfg_path


@pytest.fixture
def config(params, config_file):
    return Config(params=params, config_filename=config_file)


@pytest.fixture
def input_record(tmp_path):
    return InputRecord(
        name='test',
        dir='.',
        record_base=tmp_path,
        filepaths=[],
        driver='obsidian',
        default_atype='requirement',
        marker='REQ',
    )


def test_markdown_heading_extraction(config, input_record, tmp_path):
    contents = textwrap.dedent("""
        # Main Title
        Some paragraph text.

        ## Subheading
        Another paragraph.

        [REQ]
        Requirement contents with a heading inside:
        # Inside heading
        [id] REQ-1
        [/REQ]
    """).strip()
    filepath = tmp_path / 'test.md'
    filepath.write_text(contents, encoding='utf-8')

    extractor = ObsidianExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    # Check extracted block types
    # Expected:
    # 1. HeadingBlock: # Main Title (level 1)
    # 2. TextBlock: Some paragraph text.\n\n
    # 3. HeadingBlock: ## Subheading (level 2)
    # 4. TextBlock: Another paragraph.\n\n
    # 5. ArtifactBlock: REQ-1 (with # Inside heading intact inside its contents field)
    assert len(blocks) == 5

    assert isinstance(blocks[0], HeadingBlock)
    assert blocks[0].content == '# Main Title'
    assert blocks[0].level == 1

    assert isinstance(blocks[1], TextBlock)
    assert 'Some paragraph text' in blocks[1].content

    assert isinstance(blocks[2], HeadingBlock)
    assert blocks[2].content == '## Subheading'
    assert blocks[2].level == 2

    assert isinstance(blocks[3], TextBlock)
    assert 'Another paragraph' in blocks[3].content

    assert isinstance(blocks[4], ArtifactBlock)
    assert blocks[4].artifact.aid == 'REQ-1'
    assert '# Inside heading' in blocks[4].artifact.fields['contents']


def test_markdown_heading_exclude_filtering(config, input_record, tmp_path):
    # Case 1: string mode (exclude completely)
    input_record.exclude_elements = [ExcludeElementConfig(name='headings', mode='string')]
    contents = textwrap.dedent("""
        # Title to exclude
        Some text.
    """).strip()
    filepath = tmp_path / 'test_ex.md'
    filepath.write_text(contents, encoding='utf-8')

    extractor = ObsidianExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert not any(isinstance(b, HeadingBlock) for b in blocks)
    assert any('Some text' in b.content for b in blocks if isinstance(b, TextBlock))

    # Case 2: only mode (strip leading hashes)
    input_record.exclude_elements = [ExcludeElementConfig(name='headings', mode='only')]
    extractor = ObsidianExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    heading_blocks = [b for b in blocks if isinstance(b, HeadingBlock)]
    assert len(heading_blocks) == 1
    assert heading_blocks[0].content == 'Title to exclude'


def test_markdown_heading_rendering(params, config_file, tmp_path):
    # Write the files BEFORE instantiating config so they are scanned
    contents = textwrap.dedent("""
        # Title H1
        ## Sub H2
    """).strip()
    filepath = tmp_path / 'test_render.md'
    filepath.write_text(contents, encoding='utf-8')

    config = Config(params=params, config_filename=config_file)

    # Run build_block_tree and render_block_tree
    tree, errors = build_block_tree(config)
    assert len(errors) == 0

    rendered, _ = render_block_tree(tree, config)

    # By default, start_level is 1. If multi_record is True (default in render_block_tree),
    # the record heading gets H1, path components get H2, and H1 inside files gets shifted
    # one level deeper than path headings. Let's look for shifted headings:
    assert '# test' in rendered  # Record heading (test)
    assert '## test_render' in rendered  # Path component heading (test_render)
    assert '### Title H1' in rendered  # Shifted from H1 to H3
    assert '#### Sub H2' in rendered  # Shifted from H2 to H4
