# SPDX-License-Identifier: MIT

import pytest
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.simple_markdown import SimpleMarkdownExtractor
from syntagmax.blocks import ArtifactBlock, ErrorBlock
from syntagmax.params import Params


@pytest.fixture
def params():
    return Params(
        verbose=False,
        render_tree=False,
        ai=False,
        output='console',
        cwd='.',
        no_git=True,
        allow_dirty_worktree=False,
        language='en',
        suppress_tracing=False,
    )


@pytest.fixture
def config_file(tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        """
base = "."
[[input]]
name = "test"
dir = "."
driver = "simple-markdown"
atype = "TASK"
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
        driver='simple-markdown',
        default_atype='TASK',
        marker='TASK',
    )


def test_valid_frontmatter_explicit_id(config, input_record, tmp_path):
    """File with id: TASK-001 in frontmatter, verify artifact.aid == 'TASK-001'."""
    filepath = tmp_path / 'something.md'
    filepath.write_text(
        '---\nid: TASK-001\ntitle: My Task\n---\nBody text here.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    assert artifact.aid == 'TASK-001'


def test_filename_derived_id(config, input_record, tmp_path):
    """File without id key, filename MY-TASK-002.md, verify artifact.aid == 'MY-TASK-002'."""
    filepath = tmp_path / 'MY-TASK-002.md'
    filepath.write_text(
        '---\ntitle: Another Task\n---\nSome body.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    assert artifact.aid == 'MY-TASK-002'


def test_no_frontmatter(config, input_record, tmp_path):
    """File without --- delimiters, verify entire content in contents, filename as id, default atype."""
    filepath = tmp_path / 'PLAIN-DOC.md'
    filepath.write_text(
        'This is plain markdown.\nNo frontmatter here.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    assert artifact.aid == 'PLAIN-DOC'
    assert artifact.atype == 'TASK'
    assert 'This is plain markdown.' in artifact.fields['contents']
    assert 'No frontmatter here.' in artifact.fields['contents']


def test_malformed_yaml(config, input_record, tmp_path):
    """File with --- but invalid YAML, verify ErrorBlock is returned."""
    filepath = tmp_path / 'bad.md'
    filepath.write_text(
        '---\n: invalid: [yaml: {\n---\nBody.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ErrorBlock)


def test_atype_override(config, input_record, tmp_path):
    """Frontmatter with atype: SPEC, verify artifact.atype == 'SPEC'."""
    filepath = tmp_path / 'spec.md'
    filepath.write_text(
        '---\nid: SPEC-1\natype: SPEC\n---\nSpec body.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    assert artifact.atype == 'SPEC'


def test_list_attribute(config, input_record, tmp_path):
    """Frontmatter with tags: [a, b, c], verify field is list."""
    filepath = tmp_path / 'tagged.md'
    filepath.write_text(
        '---\nid: TAG-1\ntags: [a, b, c]\n---\nTagged body.\n',
        encoding='utf-8',
    )

    metamodel = {
        'artifacts': {
            'TASK': {
                'artifact_name': 'TASK',
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}},
                    'contents': {'name': 'contents', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}},
                    'tags': {'name': 'tags', 'presence': 'optional', 'multiple': True, 'type_info': {'type': 'string'}},
                },
            }
        },
        'traces': {},
    }

    extractor = SimpleMarkdownExtractor(config, input_record, metamodel=metamodel)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    # List attributes are added per-element as strings
    assert isinstance(artifact.fields['tags'], list)
    assert artifact.fields['tags'] == ['a', 'b', 'c']


def test_parent_field_stored(config, input_record, tmp_path):
    """Frontmatter with parent: SYS-001@abc1234, verify artifact.fields['parent'] == 'SYS-001@abc1234'."""
    filepath = tmp_path / 'child.md'
    filepath.write_text(
        '---\nid: CHILD-1\nparent: SYS-001@abc1234\n---\nChild body.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    assert artifact.fields['parent'] == 'SYS-001@abc1234'


def test_empty_body(config, input_record, tmp_path):
    """Only frontmatter no body, verify contents is empty string."""
    filepath = tmp_path / 'no-body.md'
    filepath.write_text(
        '---\nid: EMPTY-BODY\ntitle: No Body\n---\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    assert artifact.fields['contents'] == ''


def test_empty_file(config, input_record, tmp_path):
    """0 bytes, verify empty list returned."""
    filepath = tmp_path / 'empty.md'
    filepath.write_text('', encoding='utf-8')

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert blocks == []


def test_body_content_preserved(config, input_record, tmp_path):
    """Multi-line markdown body with headings, verify full content in contents."""
    body = '# Heading\n\nParagraph one.\n\n## Subheading\n\n- item 1\n- item 2'
    filepath = tmp_path / 'rich.md'
    filepath.write_text(
        f'---\nid: RICH-1\n---\n{body}\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    contents = artifact.fields['contents']
    assert '# Heading' in contents
    assert '## Subheading' in contents
    assert '- item 1' in contents
    assert '- item 2' in contents


def test_null_values_skipped(config, input_record, tmp_path):
    """Frontmatter with status: (null), verify key is not stored as 'None'."""
    filepath = tmp_path / 'null-val.md'
    filepath.write_text(
        '---\nid: NULL-1\nstatus:\n---\nBody.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    # status should not be in fields since its value is None
    if 'status' in artifact.fields:
        assert artifact.fields['status'] != 'None'


def test_case_insensitive_id(config, input_record, tmp_path):
    """Frontmatter with ID: TASK-X (uppercase), verify artifact.aid == 'TASK-X'."""
    filepath = tmp_path / 'uppercase-id.md'
    filepath.write_text(
        '---\nID: TASK-X\ntitle: Uppercase ID\n---\nBody.\n',
        encoding='utf-8',
    )

    extractor = SimpleMarkdownExtractor(config, input_record)
    blocks = extractor.extract_blocks_from_file(filepath)

    assert len(blocks) == 1
    assert isinstance(blocks[0], ArtifactBlock)
    artifact = blocks[0].artifact
    assert artifact.aid == 'TASK-X'
