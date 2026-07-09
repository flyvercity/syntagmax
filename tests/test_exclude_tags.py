# SPDX-License-Identifier: MIT
# Tests for Obsidian inline tag stripping via exclude_elements = ["tags"]

import textwrap
import pytest
from syntagmax.config import Config, InputRecord, VALID_EXCLUDE_ELEMENTS, ObsidianDriverConfig, InputConfig
from syntagmax.extractors.obsidian import ObsidianExtractor
from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.blocks import TextBlock, ArtifactBlock
from syntagmax.params import Params
from pydantic import ValidationError


# --- Fixtures ---

@pytest.fixture
def params():
    return Params(verbose=False, render_tree=False, ai=False, output='console')


@pytest.fixture
def config_file(tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        'base = "."\n[[input]]\nname = "test"\ndir = "."\ndriver = "obsidian"\natype = "REQ"\n',
        encoding='utf-8',
    )
    return cfg_path


@pytest.fixture
def config(params, config_file):
    return Config(params=params, config_filename=config_file)


@pytest.fixture
def input_record_with_tags(tmp_path):
    return InputRecord(
        name='test', dir='.', record_base=tmp_path, filepaths=[],
        driver='obsidian', default_atype='REQ', marker='REQ',
        exclude_elements=['tags'],
    )


@pytest.fixture
def input_record_no_exclude(tmp_path):
    return InputRecord(
        name='test', dir='.', record_base=tmp_path, filepaths=[],
        driver='obsidian', default_atype='REQ', marker='REQ',
        exclude_elements=[],
    )


# --- Task 1: Configuration validation tests ---

class TestConfigValidation:
    def test_tags_in_valid_exclude_elements(self):
        """'tags' should be a recognized valid element."""
        assert 'tags' in VALID_EXCLUDE_ELEMENTS

    def test_config_accepts_tags_in_global_driver(self):
        """ObsidianDriverConfig should accept 'tags' in exclude_elements."""
        cfg = ObsidianDriverConfig(exclude_elements=['tags'])
        assert 'tags' in cfg.exclude_elements

    def test_config_accepts_tags_in_input_record(self):
        """InputConfig should accept 'tags' in exclude_elements."""
        ic = InputConfig(name='test', dir='.', driver='obsidian', exclude_elements=['tags'])
        assert 'tags' in ic.exclude_elements

    def test_config_accepts_tags_combined(self):
        """Tags can be combined with other valid elements."""
        cfg = ObsidianDriverConfig(exclude_elements=['callouts', 'tags', 'frontmatter'])
        assert set(cfg.exclude_elements) == {'callouts', 'tags', 'frontmatter'}

    def test_config_rejects_invalid_element(self):
        """Invalid element names are still rejected."""
        with pytest.raises(ValidationError):
            ObsidianDriverConfig(exclude_elements=['invalid_thing'])

    def test_config_rejects_invalid_in_input(self):
        """Invalid element names in InputConfig are still rejected."""
        with pytest.raises(ValidationError):
            InputConfig(name='test', dir='.', driver='obsidian', exclude_elements=['bogus'])


# --- Task 2: Unit tests for tag stripping logic ---

class TestTagStripping:
    """Unit tests for _filter_text_content with tags exclusion."""

    def _filter(self, config, input_record, content, is_file_start=False):
        extractor = ObsidianExtractor(config, input_record)
        return extractor._filter_text_content(content, is_file_start, input_record.exclude_elements)

    # --- Basic tag stripping ---

    def test_simple_tag(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Hello #safety world\n')
        assert '#safety' not in result
        assert 'Hello' in result
        assert 'world' in result

    def test_nested_tag(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Text #project/active here\n')
        assert '#project/active' not in result
        assert 'Text' in result
        assert 'here' in result

    def test_deeply_nested_tag(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'See #parent/child/grandchild end\n')
        assert '#parent/child/grandchild' not in result
        assert 'See' in result
        assert 'end' in result

    def test_tag_with_hyphen(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Item #task-123 done\n')
        assert '#task-123' not in result
        assert 'Item' in result
        assert 'done' in result

    def test_tag_with_underscore(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Use #my_tag here\n')
        assert '#my_tag' not in result

    def test_multiple_tags_on_line(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Tags #safety #performance #active\n')
        assert '#safety' not in result
        assert '#performance' not in result
        assert '#active' not in result
        assert 'Tags' in result

    def test_tag_at_start_of_line(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, '#safety is important\n')
        assert '#safety' not in result
        assert 'is important' in result

    def test_tag_at_end_of_line(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'This is tagged #safety\n')
        assert '#safety' not in result
        assert 'This is tagged' in result

    def test_tag_only_line(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, '#safety\n')
        assert '#safety' not in result

    # --- Must NOT match: headings ---

    def test_heading_not_stripped(self, config, input_record_with_tags):
        """Headings start with # followed by space - should NOT be stripped."""
        content = '# Title\n## Section\n### Sub\n'
        result = self._filter(config, input_record_with_tags, content)
        assert '# Title\n' in result
        assert '## Section\n' in result
        assert '### Sub\n' in result

    # --- Must NOT match: hex color codes ---

    def test_hex_3_digit_not_stripped(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Color is #fff and #abc\n')
        assert '#fff' in result
        assert '#abc' in result

    def test_hex_6_digit_not_stripped(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Color is #fafafa here\n')
        assert '#fafafa' in result

    def test_hex_8_digit_not_stripped(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Alpha #ff000080 value\n')
        assert '#ff000080' in result

    def test_hex_digit_start_not_stripped(self, config, input_record_with_tags):
        """#123abc starts with a digit, so it's not matched as an Obsidian tag anyway."""
        result = self._filter(config, input_record_with_tags, 'Color #123abc here\n')
        assert '#123abc' in result

    # --- Must NOT match: URL anchors ---

    def test_url_anchor_not_stripped(self, config, input_record_with_tags):
        content = 'Visit https://example.com/#section for more\n'
        result = self._filter(config, input_record_with_tags, content)
        assert 'https://example.com/#section' in result

    def test_markdown_link_anchor_not_stripped(self, config, input_record_with_tags):
        content = 'See [docs](https://example.com/page#anchor) for details\n'
        result = self._filter(config, input_record_with_tags, content)
        assert 'https://example.com/page#anchor' in result

    def test_url_path_anchor_not_stripped(self, config, input_record_with_tags):
        content = 'Check http://site.org/docs/#getting-started today\n'
        result = self._filter(config, input_record_with_tags, content)
        assert 'http://site.org/docs/#getting-started' in result

    # --- Must preserve: fenced code blocks ---

    def test_tags_in_fenced_code_preserved(self, config, input_record_with_tags):
        content = 'Before #remove\n```\n#keep_this_tag\n```\nAfter #remove\n'
        result = self._filter(config, input_record_with_tags, content)
        assert '#keep_this_tag' in result
        assert '#remove' not in result

    def test_tags_in_fenced_code_with_language(self, config, input_record_with_tags):
        content = '```python\ncomment = "#mytag"\n```\n'
        result = self._filter(config, input_record_with_tags, content)
        assert '#mytag' in result

    # --- Must preserve: inline code blocks ---

    def test_tags_in_inline_code_preserved(self, config, input_record_with_tags):
        content = 'Use `#safety` in your notes\n'
        result = self._filter(config, input_record_with_tags, content)
        assert '`#safety`' in result

    def test_tags_in_double_backtick_preserved(self, config, input_record_with_tags):
        content = 'Use ``#project/active`` tag\n'
        result = self._filter(config, input_record_with_tags, content)
        assert '``#project/active``' in result

    def test_mixed_inline_code_and_tags(self, config, input_record_with_tags):
        content = 'Strip #remove but keep `#keep` here #also_remove\n'
        result = self._filter(config, input_record_with_tags, content)
        assert '#remove' not in result
        assert '#also_remove' not in result
        assert '`#keep`' in result

    # --- Spacing behavior ---

    def test_no_double_spaces_after_removal(self, config, input_record_with_tags):
        result = self._filter(config, input_record_with_tags, 'Hello #tag world\n')
        assert '  ' not in result

    def test_newlines_preserved(self, config, input_record_with_tags):
        content = 'Line 1 #tag1\nLine 2 #tag2\nLine 3\n'
        result = self._filter(config, input_record_with_tags, content)
        lines = result.splitlines()
        assert len(lines) == 3

    # --- No stripping when 'tags' not in exclude ---

    def test_no_stripping_without_config(self, config, input_record_no_exclude):
        content = 'Hello #safety world\n'
        result = self._filter(config, input_record_no_exclude, content)
        assert '#safety' in result


# --- Task 3: Integration tests ---

class TestTagStrippingIntegration:
    """Integration tests verifying full extraction pipeline with tags exclusion."""

    def test_text_blocks_stripped_artifact_untouched(self, config, input_record_with_tags, tmp_path):
        """Tags in TextBlocks are stripped but artifact content is untouched."""
        content = textwrap.dedent("""\
        Preamble with #safety tag.

        [REQ]
        Requirement body with #performance tag.
        [id] REQ-001
        ```yaml
        attrs:
          priority: high
        ```

        Postamble #cleanup here.
        """)

        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record_with_tags)
        blocks = extractor.extract_blocks_from_file(filepath)

        # Check TextBlocks have tags stripped
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        for tb in text_blocks:
            assert '#safety' not in tb.content
            assert '#cleanup' not in tb.content

        # Check ArtifactBlock content is untouched
        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.fields['contents'].strip() == 'Requirement body with #performance tag.'

    def test_combined_callouts_and_tags(self, config, tmp_path):
        """Combining 'callouts' and 'tags' excludes both."""
        record = InputRecord(
            name='test', dir='.', record_base=tmp_path, filepaths=[],
            driver='obsidian', default_atype='REQ', marker='REQ',
            exclude_elements=['callouts', 'tags'],
        )

        content = textwrap.dedent("""\
        Some text #remove_tag here.
        > This callout should be removed.
        Still here #another_tag end.
        """)

        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        combined_text = ''.join(tb.content for tb in text_blocks)

        assert '#remove_tag' not in combined_text
        assert '#another_tag' not in combined_text
        assert 'callout' not in combined_text
        assert 'Some text' in combined_text
        assert 'Still here' in combined_text

    def test_tags_in_code_block_preserved_integration(self, config, input_record_with_tags, tmp_path):
        """Tags inside fenced code blocks remain after full extraction."""
        content = textwrap.dedent("""\
        Outside #strip_me

        ```
        Inside #keep_me
        ```

        Also outside #strip_too
        """)

        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(config, input_record_with_tags)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        combined_text = ''.join(tb.content for tb in text_blocks)

        assert '#keep_me' in combined_text
        assert '#strip_me' not in combined_text
        assert '#strip_too' not in combined_text

    def test_config_driven_exclude_tags(self, params, tmp_path):
        """Full config-driven test with exclude_elements = ["tags"] in TOML."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(textwrap.dedent("""\
        base = "."

        [drivers.obsidian]
        exclude_elements = ["tags"]

        [[input]]
        name = "reqs"
        dir = "."
        driver = "obsidian"
        atype = "REQ"
        """), encoding='utf-8')

        md_path = tmp_path / 'REQ-001.md'
        md_path.write_text(textwrap.dedent("""\
        Notes #internal #draft

        [REQ]
        The system shall do X.
        [id] REQ-001
        ```yaml
        attrs:
          status: active
        ```
        """), encoding='utf-8')

        config = Config(params=params, config_filename=cfg_path)
        record = config.input_records()[0]
        assert 'tags' in record.exclude_elements

        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(md_path)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        combined = ''.join(tb.content for tb in text_blocks)
        assert '#internal' not in combined
        assert '#draft' not in combined

        # Artifact untouched
        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'
