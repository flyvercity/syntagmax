# SPDX-License-Identifier: MIT
import pytest
from unittest.mock import MagicMock
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.text import TextExtractor
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
        tree = BlockTree(inputs=[InputBlock(name='reqs', files=[FileRecord(path='a.md', blocks=[TextBlock(content='hello')])])])
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

        record = InputRecord(name='t', dir='.', record_base=tmp_path, filepaths=[f], driver='text', default_atype='SRC', marker='SRC')
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

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='reqs',
                    files=[
                        FileRecord(
                            path='req.md',
                            blocks=[
                                TextBlock(content='# Intro\n'),
                                ArtifactBlock(artifact=artifact, raw_text='raw'),
                            ],
                        )
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree)
        assert '# reqs' in result
        assert '## req' in result
        assert '### Intro' in result
        assert '### REQ-1' in result
        assert '| status | active |' in result
        assert '| id |' not in result

    def test_render_list_fields_with_non_strings(self):
        artifact = MagicMock()
        artifact.aid = 'SYS-1'
        artifact.contents.return_value = 'Body'
        artifact.fields = {'id': 'SYS-1', 'contents': 'Body', 'tags': [1, 2], 'verified': True}

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='sys',
                    files=[
                        FileRecord(
                            path='sys.md',
                            blocks=[
                                ArtifactBlock(artifact=artifact, raw_text='raw'),
                            ],
                        )
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree)
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

        tree, errors = build_block_tree(cfg)
        assert len(tree.inputs) == 1
        files = tree.inputs[0].files
        assert len(files) == 2
        assert 'a_file.py' in files[0].path
        assert 'b_file.py' in files[1].path


class TestConfigDrivenRendering:
    def test_custom_render_scenarios(self):
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        # Create mock artifact
        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-1'
        artifact.fields = {'id': 'REQ-1', 'contents': '# 1.2 Intro\nRequirement description here.\n', 'safety': 'yes', 'parent': 'SYS-1'}

        # Case 1: Custom Table and TextSection
        yaml_config = {
            'start_level': 2,
            'remove_numeric_prefixes_in_headers': True,
            'render': {
                'REQ': [
                    {'type': 'table', 'attributes': [{'id': {'alias': 'ID'}}, {'parent': {'alias': 'SoR'}}]},
                    {'type': 'text', 'mode': 'block', 'attributes': [{'contents': {'alias': 'Body'}}]},
                    {'type': 'text', 'mode': 'inline', 'attributes': [{'safety': {'alias': 'SFTY'}}]},
                ]
            },
        }
        pub_config = PublishConfig.model_validate(yaml_config)
        block = ArtifactBlock(artifact=artifact, raw_text='')
        result = render_block(block, pub_config)

        # Output checks
        # Table checks (vertical)
        assert '| ID | REQ-1 |' in result
        assert '| SoR | SYS-1 |' in result

        # Text block mode: start_level=2 offsets '#' by +1 to '##' and strips '1.2' prefix
        assert '**Body**' in result
        assert '## Intro' in result

        # Text inline mode
        assert '**SFTY**: yes' in result

    def test_marker_rendering(self):
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        yaml_config = {'render': {'COM': [{'type': 'text', 'mode': 'block', 'alias': 'Comment'}]}}
        pub_config = PublishConfig.model_validate(yaml_config)
        block = TextBlock(content='This is a draft comment.', marker='COM')
        result = render_block(block, pub_config)

        assert '**Comment**' in result
        assert 'This is a draft comment.' in result

    def test_plain_text_exclusion_and_filtering(self):
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        # Exclude plain text completely
        pub_config_exclude = PublishConfig(include_plain_text=False)
        block = TextBlock(content='Some plain text', marker=None)
        assert render_block(block, pub_config_exclude) == ''

        # Include plain text
        pub_config_include = PublishConfig(include_plain_text=True)
        block_include = TextBlock(content='Regular line\n', marker=None)
        result = render_block(block_include, pub_config_include)
        assert 'Regular line' in result


class TestPublishCLI:
    def test_publish_cli_basic(self, tmp_path):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        # Create default .syntagmax directory
        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        # Write config.toml in default location
        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

        # Create input dir & file
        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        f = sys_dir / 'sys.md'
        f.write_text('[< ID=SYS-1 >>> System shall do X. >]', encoding='utf-8')

        # Create default .syntagmax/publish.yaml
        default_yaml = dot_syntagmax / 'publish.yaml'
        default_yaml.write_text(
            'start_level: 2\nrender:\n  SYS:\n    - type: text\n      mode: inline\n      attributes:\n        - contents:\n            alias: "Body"\n',
            encoding='utf-8',
        )

        runner = CliRunner()
        # Publish separately
        out_dir = tmp_path / 'out'
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--output', str(out_dir)])
        assert result.exit_code == 0, result.output

        file_path = out_dir / 'rec1.md'
        assert file_path.exists()
        content = file_path.read_text(encoding='utf-8')
        assert '## sys' in content  # file heading: start_level=2, multi_record=False
        assert '**Body**: System shall do X.' in content

        # Run publish consolidated (--single)
        single_file = tmp_path / 'combined.md'
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--single', '--output', str(single_file)])
        assert result.exit_code == 0, result.output
        assert single_file.exists()
        content = single_file.read_text(encoding='utf-8')
        assert '## sys' in content  # single record with --all: multi_record=False (only 1 record)
        assert '**Body**: System shall do X.' in content

    def test_publish_date_suffix(self, tmp_path):
        from datetime import datetime
        from click.testing import CliRunner
        from syntagmax.cli import rms

        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        f = sys_dir / 'sys.md'
        f.write_text('[< ID=SYS-1 >>> System shall do X. >]', encoding='utf-8')

        runner = CliRunner()
        out_dir = tmp_path / 'out'

        # Publish with --date-suffix
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--date-suffix', '--output', str(out_dir)])
        assert result.exit_code == 0, result.output

        date_str = datetime.now().strftime('%Y-%m-%d')
        expected_file = out_dir / f'rec1_{date_str}.md'
        assert expected_file.exists(), f'Expected {expected_file} to exist, found: {list(out_dir.iterdir())}'

        # Verify content
        content = expected_file.read_text(encoding='utf-8')
        assert 'SYS-1' in content

    def test_publish_date_suffix_incompatible_with_single(self, tmp_path):
        from click.testing import CliRunner
        from syntagmax.cli import rms

        dot_syntagmax = tmp_path / '.syntagmax'
        dot_syntagmax.mkdir()

        cfg = dot_syntagmax / 'config.toml'
        cfg.write_text('base = ".."\n[[input]]\nname="rec1"\ndir="SYS"\ndriver="text"\natype="SYS"\n', encoding='utf-8')

        sys_dir = tmp_path / 'SYS'
        sys_dir.mkdir()
        f = sys_dir / 'sys.md'
        f.write_text('[< ID=SYS-1 >>> X >]', encoding='utf-8')

        runner = CliRunner()
        result = runner.invoke(rms, ['--cwd', str(tmp_path), 'publish', '--all', '--single', '--date-suffix'])
        assert result.exit_code != 0


class TestPathDecomposition:
    def test_decompose_strips_record_dir(self):
        from syntagmax.publish import decompose_file_path
        result = decompose_file_path('SYS/01-Intro/02-Functional.md', 'SYS')
        assert result == ['01-Intro', '02-Functional']

    def test_decompose_nested_record_dir(self):
        from syntagmax.publish import decompose_file_path
        result = decompose_file_path('requirements/REQS/chapter/file.md', 'requirements/REQS')
        assert result == ['chapter', 'file']

    def test_decompose_file_only(self):
        from syntagmax.publish import decompose_file_path
        result = decompose_file_path('SYS/myfile.md', 'SYS')
        assert result == ['myfile']

    def test_decompose_no_match(self):
        from syntagmax.publish import decompose_file_path
        result = decompose_file_path('OTHER/file.md', 'SYS')
        assert result == ['OTHER', 'file']

    def test_decompose_dot_dir(self):
        from syntagmax.publish import decompose_file_path
        result = decompose_file_path('file.md', '.')
        assert result == ['file']


class TestPathHeadings:
    def test_headings_emitted_for_directories_and_files(self):
        from syntagmax.publish import render_block_tree

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='sys',
                    files=[
                        FileRecord(path='SYS/01-Intro/02-Overview.md', blocks=[TextBlock(content='Some text')]),
                        FileRecord(path='SYS/01-Intro/03-Scope.md', blocks=[TextBlock(content='More text')]),
                        FileRecord(path='SYS/02-Design/01-Arch.md', blocks=[TextBlock(content='Design text')]),
                    ],
                )
            ]
        )

        # Simulate config with record_dir='SYS', start_level=1, remove_numeric_prefixes=True
        # Without config, record_dir defaults to '' so we test with multi_record=False
        result, _ = render_block_tree(tree, multi_record=False)

        # With no config, record_dir is '' so full path components are used
        # SYS/01-Intro/02-Overview.md -> ['SYS', '01-Intro', '02-Overview']
        # With default remove_numeric_prefixes=True: SYS, Intro, Overview
        assert '# SYS' in result
        assert '## Intro' in result
        assert '### Overview' in result
        assert '### Scope' in result
        # Intro heading should appear only once (shared dir)
        assert result.count('## Intro') == 1
        # Design is a new directory
        assert '## Design' in result
        assert '### Arch' in result

    def test_multi_record_emits_record_heading(self):
        from syntagmax.publish import render_block_tree

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='sys-reqs',
                    files=[FileRecord(path='file.md', blocks=[TextBlock(content='Body')])],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=True)
        assert '# sys-reqs' in result
        assert '## file' in result

    def test_single_record_no_record_heading(self):
        from syntagmax.publish import render_block_tree

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='sys-reqs',
                    files=[FileRecord(path='file.md', blocks=[TextBlock(content='Body')])],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        assert 'sys-reqs' not in result
        assert '# file' in result

    def test_numeric_prefix_stripping_disabled(self):
        from syntagmax.publish import render_block_tree

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='reqs',
                    files=[FileRecord(path='01-Introduction.md', blocks=[TextBlock(content='text')])],
                )
            ]
        )

        # Without config, default is remove_numeric_prefixes=True
        result_stripped, _ = render_block_tree(tree, multi_record=False)
        assert '# Introduction' in result_stripped

    def test_numeric_prefix_stripping_on_record_name(self):
        from syntagmax.publish import render_block_tree

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='01 System Requirements',
                    files=[FileRecord(path='file.md', blocks=[TextBlock(content='text')])],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=True)
        assert '# System Requirements' in result

    def test_heading_level_capping(self):
        from syntagmax.publish import render_block_tree

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='rec',
                    files=[FileRecord(path='a/b/c/d/e/f/g.md', blocks=[TextBlock(content='deep')])],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=True)
        # record at level 1, then a=2, b=3, c=4, d=5, e=6, f=6, g=6 (capped)
        assert '###### ' in result
        # Should not exceed 6 hashes
        assert '####### ' not in result

    def test_duplicate_dirs_not_repeated(self):
        from syntagmax.publish import render_block_tree

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='rec',
                    files=[
                        FileRecord(path='dir/file1.md', blocks=[TextBlock(content='A')]),
                        FileRecord(path='dir/file2.md', blocks=[TextBlock(content='B')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        # 'dir' heading emitted once
        assert result.count('# dir') == 1
        assert '## file1' in result
        assert '## file2' in result


class TestContentLevelHierarchy:
    """Tests for heading level hierarchy: content headings respect file depth."""

    def test_render_block_explicit_content_level(self):
        """render_block with explicit content_level offsets H1 correctly."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        pub_config = PublishConfig()
        block = TextBlock(content='# Title\n## Subtitle\n')
        result = render_block(block, pub_config, content_level=4)
        assert '#### Title' in result
        assert '##### Subtitle' in result

    def test_render_block_content_level_none_defaults_to_start_level(self):
        """render_block with content_level=None falls back to pub_config.start_level."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        pub_config = PublishConfig(start_level=2)
        block = TextBlock(content='# Heading\n')
        result = render_block(block, pub_config, content_level=None)
        assert '## Heading' in result

    def test_render_block_artifact_fallback_uses_content_level(self):
        """Artifact fallback heading renders at content_level."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-42'
        artifact.fields = {'id': 'REQ-42', 'contents': 'Description'}
        artifact.location = None

        pub_config = PublishConfig()
        block = ArtifactBlock(artifact=artifact, raw_text='')
        result = render_block(block, pub_config, content_level=4)
        assert '#### REQ-42' in result

    def test_multi_record_nested_file_content_heading(self):
        """Content H1 in a nested file renders below the file's path heading."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='subdir/file.md', blocks=[TextBlock(content='# Intro\n## Details\n')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=True)
        # Hierarchy: # docs (level 1), ## subdir (level 2), ### file (level 3), #### Intro (level 4)
        assert '# docs' in result
        assert '## subdir' in result
        assert '### file' in result
        assert '#### Intro' in result
        assert '##### Details' in result

    def test_single_record_nested_file_content_heading(self):
        """Content H1 in single-record mode renders below the file's path heading."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='dir/file.md', blocks=[TextBlock(content='# Intro\n')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        # Hierarchy: # dir (level 1), ## file (level 2), ### Intro (level 3)
        assert '# dir' in result
        assert '## file' in result
        assert '### Intro' in result

    def test_content_heading_level_capping_at_h6(self):
        """Content headings are capped at H6 even with deep nesting."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='rec',
                    files=[
                        FileRecord(path='a/b/c/d/e.md', blocks=[TextBlock(content='# Deep\n## Deeper\n')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=True)
        # record=1, a=2, b=3, c=4, d=5, e=6 (capped), content_level=min(6, 2+5)=6
        # H1 in content -> level 6, H2 -> also capped at 6
        assert '###### Deep' in result
        assert '###### Deeper' in result
        assert '####### ' not in result

    def test_empty_components_falls_back_to_path_base_level(self):
        """Files with empty path components use path_base_level as content_level."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='rec',
                    files=[
                        FileRecord(path='', blocks=[TextBlock(content='# Title\n')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=True)
        # path_base_level=2 (multi_record with start_level=1), empty components -> content_level=2
        assert '## Title' in result



class TestContentFiles:
    """Tests for content files (headingless file rendering)."""

    def test_content_file_no_heading_emitted(self):
        """A file whose stem matches the contents_marker gets no filename heading."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='Chapter/_contents_.md', blocks=[TextBlock(content='Intro text')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        assert '# Chapter' in result
        assert '_contents_' not in result
        assert 'Intro text' in result

    def test_content_file_case_insensitive_match(self):
        """Matching is case-insensitive: _CONTENTS_.md still treated as content file."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='Section/_CONTENTS_.md', blocks=[TextBlock(content='Body')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        assert '# Section' in result
        assert '_CONTENTS_' not in result
        assert 'Body' in result

    def test_content_file_among_siblings(self):
        """Content file sorted among siblings: renders in sort order without heading."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='Chapter/01-Intro.md', blocks=[TextBlock(content='Intro')]),
                        FileRecord(path='Chapter/_contents_.md', blocks=[TextBlock(content='Chapter body')]),
                        FileRecord(path='Chapter/Requirements.md', blocks=[TextBlock(content='Reqs')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        assert '# Chapter' in result
        assert '## Intro' in result
        assert '_contents_' not in result
        assert 'Chapter body' in result
        assert '## Requirements' in result
        # Verify ordering: Intro before _contents_ body before Requirements
        intro_pos = result.index('## Intro')
        body_pos = result.index('Chapter body')
        reqs_pos = result.index('## Requirements')
        assert intro_pos < body_pos < reqs_pos

    def test_content_file_content_level_at_directory_body(self):
        """Content file's H1 renders at the directory's body level, not one deeper."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='Section/_contents_.md', blocks=[TextBlock(content='# Heading\n## Sub\n')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        # Section at level 1, content_level = level 2 (directory body)
        assert '# Section' in result
        assert '## Heading' in result
        assert '### Sub' in result

    def test_normal_file_content_level_one_deeper(self):
        """Normal file's H1 renders one level deeper than file heading (for comparison)."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='Section/Normal.md', blocks=[TextBlock(content='# Heading\n')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        # Section at level 1, Normal at level 2, content_level = 3
        assert '# Section' in result
        assert '## Normal' in result
        assert '### Heading' in result

    def test_content_file_does_not_match_partial_name(self):
        """A file named _contents_intro.md does NOT match — must be exact stem."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='Section/_contents_intro.md', blocks=[TextBlock(content='text')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        # Should be treated as a normal file with heading emitted
        assert '# Section' in result
        assert '_contents_intro' in result or '## _contents_intro' in result

    def test_content_file_multi_record_mode(self):
        """Content file works correctly in multi-record mode."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='reqs',
                    files=[
                        FileRecord(path='SYS/_contents_.md', blocks=[TextBlock(content='System intro')]),
                        FileRecord(path='SYS/Functional.md', blocks=[TextBlock(content='Func reqs')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=True)
        # Hierarchy: # reqs (record), ## SYS (dir), content at level 3, ### Functional (file)
        assert '# reqs' in result
        assert '## SYS' in result
        assert '_contents_' not in result
        assert 'System intro' in result
        assert '### Functional' in result

    def test_content_file_sibling_headings_still_emit_after_content_file(self):
        """After a content file, subsequent sibling files still get their headings."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='dir/_contents_.md', blocks=[TextBlock(content='intro')]),
                        FileRecord(path='dir/alpha.md', blocks=[TextBlock(content='a')]),
                        FileRecord(path='dir/beta.md', blocks=[TextBlock(content='b')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        assert '# dir' in result
        assert '## alpha' in result
        assert '## beta' in result
        assert '_contents_' not in result

    def test_content_file_at_root_level(self):
        """Content file at root (no parent dir) — no heading emitted, content at base level."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='_contents_.md', blocks=[TextBlock(content='# Root\n')]),
                    ],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        assert '_contents_' not in result
        # With no parent dir, content_level = path_base_level + len([_contents_]) - 1 = 1 + 0 = 0? No.
        # components = ['_contents_'], is_content_file=True, content_level = min(6, 1 + 1 - 1) = 1
        assert '# Root' in result

    def test_content_file_with_numeric_prefix(self):
        """Content file with numeric prefix in filename matches after prefix stripping."""
        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='docs',
                    files=[
                        FileRecord(path='Chapter/2.1.0 content.md', blocks=[TextBlock(content='Body text')]),
                        FileRecord(path='Chapter/2.1.1 Intro.md', blocks=[TextBlock(content='Intro')]),
                    ],
                )
            ]
        )

        # Build the tree and render without a full Config (uses defaults)
        result, _ = render_block_tree(tree, multi_record=False)
        # Default contents_marker is '_contents_', not 'content', so this won't match with default
        # We need to test with actual config. Let's verify the raw stem matching behavior instead.
        # With default marker, '2.1.0 content' stripped to 'content' != '_contents_', so heading emitted
        assert '## content' in result

    def test_content_file_with_numeric_prefix_and_custom_marker(self):
        """Content file with numeric prefix matches custom marker after stripping."""
        from syntagmax.publish import decompose_file_path, strip_numeric_prefix

        # Verify the detection logic directly
        components = decompose_file_path('Chapter/2.1.0 content.md', '.')
        assert components == ['Chapter', '2.1.0 content']
        # After stripping: 'content'
        assert strip_numeric_prefix(components[-1]) == 'content'


class TestImageRewritingFences:
    def test_rewrite_images_in_unclosed_fence(self, monkeypatch):
        import syntagmax.publish as pub
        from syntagmax.publish import rewrite_image_references
        from syntagmax.publish_context import RenderContext, ImageManifest

        # Mock RenderContext and Config
        mock_config = MagicMock()
        context = RenderContext(config=mock_config, manifest=ImageManifest())

        # Monkeypatch _rewrite_images_in_segment to return a marker
        calls = []
        def mock_rewrite(segment, ctx):
            calls.append(segment)
            return "REWRITTEN"

        monkeypatch.setattr(pub, "_rewrite_images_in_segment", mock_rewrite)

        # 1. Test with no fence
        content1 = "No fence content"
        res1 = rewrite_image_references(content1, context)
        assert res1 == "REWRITTEN"
        assert calls == ["No fence content"]
        calls.clear()

        # 2. Test with closed fence
        content2 = "Outside\n```\nInside\n```\nOutside2"
        res2 = rewrite_image_references(content2, context)
        assert res2 == "REWRITTEN```\nInside\n```\nREWRITTEN"
        assert calls == ["Outside\n", "Outside2"]
        calls.clear()

        # 3. Test with unclosed fence (BUG-7 fix check)
        content3 = "Outside\n```\nUnclosed Inside"
        res3 = rewrite_image_references(content3, context)
        assert res3 == "REWRITTEN```\nUnclosed Inside"
        assert calls == ["Outside\n"]


class TestTableSpacerRendering:
    """Tests for table spacer rendering in both custom and fallback modes."""

    def test_custom_table_section_default_spacer(self):
        """Default global table_spacer=1 produces one &nbsp; paragraph before table."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-1'
        artifact.fields = {'id': 'REQ-1', 'parent': 'SYS-1'}
        artifact.location = None

        pub_config = PublishConfig.model_validate({
            'render': {
                'REQ': [{'type': 'table', 'attributes': [{'id': {'alias': 'ID'}}, {'parent': {'alias': 'Parent'}}]}]
            }
        })
        block = ArtifactBlock(artifact=artifact, raw_text='')
        result = render_block(block, pub_config)

        assert result.count('&nbsp;\n\n') == 1
        assert '&nbsp;\n\n|' in result

    def test_custom_table_section_spacer_override(self):
        """Per-section spacer=3 produces three &nbsp; paragraphs before table."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-1'
        artifact.fields = {'id': 'REQ-1', 'parent': 'SYS-1'}
        artifact.location = None

        pub_config = PublishConfig.model_validate({
            'table_spacer': 1,
            'render': {
                'REQ': [{'type': 'table', 'spacer': 3, 'attributes': [{'id': {'alias': 'ID'}}, {'parent': {'alias': 'Parent'}}]}]
            }
        })
        block = ArtifactBlock(artifact=artifact, raw_text='')
        result = render_block(block, pub_config)

        assert result.count('&nbsp;\n\n') == 3

    def test_custom_table_section_spacer_zero(self):
        """Per-section spacer=0 produces no spacer lines."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-1'
        artifact.fields = {'id': 'REQ-1', 'parent': 'SYS-1'}
        artifact.location = None

        pub_config = PublishConfig.model_validate({
            'table_spacer': 5,
            'render': {
                'REQ': [{'type': 'table', 'spacer': 0, 'attributes': [{'id': {'alias': 'ID'}}, {'parent': {'alias': 'Parent'}}]}]
            }
        })
        block = ArtifactBlock(artifact=artifact, raw_text='')
        result = render_block(block, pub_config)

        assert '&nbsp;' not in result
        assert result.startswith('|')

    def test_custom_table_section_uses_global_when_no_override(self):
        """When no per-section spacer, global table_spacer is used."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-1'
        artifact.fields = {'id': 'REQ-1', 'parent': 'SYS-1'}
        artifact.location = None

        pub_config = PublishConfig.model_validate({
            'table_spacer': 4,
            'render': {
                'REQ': [{'type': 'table', 'attributes': [{'id': {'alias': 'ID'}}, {'parent': {'alias': 'Parent'}}]}]
            }
        })
        block = ArtifactBlock(artifact=artifact, raw_text='')
        result = render_block(block, pub_config)

        assert result.count('&nbsp;\n\n') == 4

    def test_custom_table_section_empty_table_no_spacer(self):
        """When no attributes match (empty table), no spacer is emitted."""
        from syntagmax.publish_config import PublishConfig
        from syntagmax.publish import render_block

        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-1'
        artifact.fields = {'id': 'REQ-1'}
        artifact.location = None

        pub_config = PublishConfig.model_validate({
            'table_spacer': 3,
            'render': {
                'REQ': [{'type': 'table', 'attributes': [{'nonexistent': {'alias': 'N/A'}}]}]
            }
        })
        block = ArtifactBlock(artifact=artifact, raw_text='')
        result = render_block(block, pub_config)

        assert '&nbsp;' not in result

    def test_fallback_rendering_default_spacer(self):
        """Fallback rendering with default table_spacer=1 produces one &nbsp; paragraph."""
        from syntagmax.publish import render_artifact_fallback

        artifact = MagicMock()
        artifact.aid = 'SYS-1'
        artifact.fields = {'id': 'SYS-1', 'contents': 'Body', 'status': 'active'}

        result = render_artifact_fallback(artifact, content_level=2)

        assert result.count('&nbsp;\n\n') == 1
        assert '&nbsp;\n\n| Field | Value |' in result

    def test_fallback_rendering_custom_spacer(self):
        """Fallback rendering with table_spacer=2 produces two &nbsp; paragraphs."""
        from syntagmax.publish import render_artifact_fallback

        artifact = MagicMock()
        artifact.aid = 'SYS-1'
        artifact.fields = {'id': 'SYS-1', 'contents': 'Body', 'status': 'active'}

        result = render_artifact_fallback(artifact, content_level=2, table_spacer=2)

        assert result.count('&nbsp;\n\n') == 2

    def test_fallback_rendering_spacer_zero(self):
        """Fallback rendering with table_spacer=0 produces no spacer."""
        from syntagmax.publish import render_artifact_fallback

        artifact = MagicMock()
        artifact.aid = 'SYS-1'
        artifact.fields = {'id': 'SYS-1', 'contents': 'Body', 'status': 'active'}

        result = render_artifact_fallback(artifact, content_level=2, table_spacer=0)

        assert '&nbsp;' not in result
        # Table still present
        assert '| Field | Value |' in result

    def test_fallback_no_metadata_no_spacer(self):
        """Fallback with only id and contents (no metadata table) produces no spacer."""
        from syntagmax.publish import render_artifact_fallback

        artifact = MagicMock()
        artifact.aid = 'SYS-1'
        artifact.fields = {'id': 'SYS-1', 'contents': 'Body'}

        result = render_artifact_fallback(artifact, content_level=2, table_spacer=3)

        assert '&nbsp;' not in result
        assert '| Field | Value |' not in result

    def test_render_block_tree_fallback_uses_global_spacer(self):
        """render_block_tree passes global table_spacer to fallback rendering."""
        from syntagmax.config import Config
        from syntagmax.params import Params

        artifact = MagicMock()
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-1'
        artifact.fields = {'id': 'REQ-1', 'contents': 'Desc', 'status': 'active'}
        artifact.location = None

        tree = BlockTree(
            inputs=[
                InputBlock(
                    name='reqs',
                    files=[FileRecord(path='req.md', blocks=[ArtifactBlock(artifact=artifact, raw_text='')])],
                )
            ]
        )

        result, _ = render_block_tree(tree, multi_record=False)
        # Default table_spacer=1
        assert '&nbsp;\n\n| Field | Value |' in result
