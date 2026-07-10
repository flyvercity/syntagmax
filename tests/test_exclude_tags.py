# SPDX-License-Identifier: MIT
# Tests for Obsidian element exclusion with configurable removal modes

import textwrap
import pytest
from syntagmax.config import (
    Config, InputRecord, VALID_EXCLUDE_ELEMENTS, VALID_EXCLUDE_MODES,
    ObsidianDriverConfig, InputConfig, ExcludeElementConfig,
)
from syntagmax.extractors.obsidian import ObsidianExtractor
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
def input_record_tags_only(tmp_path):
    """Tags with mode=only (strip inline, keep surrounding text)."""
    return InputRecord(
        name='test', dir='.', record_base=tmp_path, filepaths=[],
        driver='obsidian', default_atype='REQ', marker='REQ',
        exclude_elements=[ExcludeElementConfig(name='tags', mode='only')],
    )


@pytest.fixture
def input_record_tags_string(tmp_path):
    """Tags with mode=string (remove entire line if tag present)."""
    return InputRecord(
        name='test', dir='.', record_base=tmp_path, filepaths=[],
        driver='obsidian', default_atype='REQ', marker='REQ',
        exclude_elements=[ExcludeElementConfig(name='tags', mode='string')],
    )


@pytest.fixture
def input_record_tags_string_on_start(tmp_path):
    """Tags with mode=string-on-start (remove line if tag starts it, else strip inline)."""
    return InputRecord(
        name='test', dir='.', record_base=tmp_path, filepaths=[],
        driver='obsidian', default_atype='REQ', marker='REQ',
        exclude_elements=[ExcludeElementConfig(name='tags', mode='string-on-start')],
    )


@pytest.fixture
def input_record_no_exclude(tmp_path):
    return InputRecord(
        name='test', dir='.', record_base=tmp_path, filepaths=[],
        driver='obsidian', default_atype='REQ', marker='REQ',
        exclude_elements=[],
    )



# --- Configuration validation tests ---

class TestConfigValidation:
    def test_tags_in_valid_exclude_elements(self):
        assert 'tags' in VALID_EXCLUDE_ELEMENTS

    def test_all_modes_defined(self):
        assert VALID_EXCLUDE_MODES == {'only', 'string', 'string-on-start'}

    def test_config_accepts_structured_format(self):
        cfg = ObsidianDriverConfig(
            exclude_elements=[{'name': 'tags', 'mode': 'string'}]
        )
        assert cfg.exclude_elements[0].name == 'tags'
        assert cfg.exclude_elements[0].mode == 'string'

    def test_config_default_mode_is_string_on_start(self):
        cfg = ObsidianDriverConfig(
            exclude_elements=[{'name': 'callouts'}]
        )
        assert cfg.exclude_elements[0].mode == 'string-on-start'

    def test_config_accepts_combined_elements(self):
        cfg = ObsidianDriverConfig(
            exclude_elements=[
                {'name': 'callouts', 'mode': 'only'},
                {'name': 'tags', 'mode': 'string'},
                {'name': 'frontmatter'},
            ]
        )
        names = {e.name for e in cfg.exclude_elements}
        assert names == {'callouts', 'tags', 'frontmatter'}

    def test_config_rejects_invalid_element_name(self):
        with pytest.raises(ValidationError):
            ObsidianDriverConfig(exclude_elements=[{'name': 'invalid_thing'}])

    def test_config_rejects_invalid_mode(self):
        with pytest.raises(ValidationError):
            ObsidianDriverConfig(exclude_elements=[{'name': 'tags', 'mode': 'bad'}])

    def test_config_rejects_duplicate_names(self):
        with pytest.raises(ValidationError):
            ObsidianDriverConfig(
                exclude_elements=[
                    {'name': 'tags', 'mode': 'only'},
                    {'name': 'tags', 'mode': 'string'},
                ]
            )

    def test_input_config_accepts_structured_format(self):
        ic = InputConfig(
            name='test', dir='.', driver='obsidian',
            exclude_elements=[{'name': 'tags', 'mode': 'string-on-start'}],
        )
        assert ic.exclude_elements[0].name == 'tags'

    def test_input_config_rejects_plain_string(self):
        with pytest.raises(ValidationError):
            InputConfig(
                name='test', dir='.', driver='obsidian',
                exclude_elements=['tags'],
            )

    def test_input_config_rejects_duplicate_names(self):
        with pytest.raises(ValidationError):
            InputConfig(
                name='test', dir='.', driver='obsidian',
                exclude_elements=[{'name': 'tags'}, {'name': 'tags', 'mode': 'only'}],
            )

    def test_merge_logic_per_record_overrides_global(self, params, tmp_path):
        """Per-record mode takes precedence over global mode for same element."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(textwrap.dedent("""\
        base = "."

        [drivers.obsidian]
        exclude_elements = [{name = "tags", mode = "only"}]

        [[input]]
        name = "reqs"
        dir = "."
        driver = "obsidian"
        atype = "REQ"
        exclude_elements = [{name = "tags", mode = "string"}]
        """), encoding='utf-8')

        config = Config(params=params, config_filename=cfg_path)
        record = config.input_records()[0]
        tag_elem = next(e for e in record.exclude_elements if e.name == 'tags')
        assert tag_elem.mode == 'string'

    def test_merge_logic_union_of_elements(self, params, tmp_path):
        """Union: global and per-record elements are merged."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(textwrap.dedent("""\
        base = "."

        [drivers.obsidian]
        exclude_elements = [{name = "frontmatter"}]

        [[input]]
        name = "reqs"
        dir = "."
        driver = "obsidian"
        atype = "REQ"
        exclude_elements = [{name = "callouts", mode = "only"}]
        """), encoding='utf-8')

        config = Config(params=params, config_filename=cfg_path)
        record = config.input_records()[0]
        names = {e.name for e in record.exclude_elements}
        assert names == {'frontmatter', 'callouts'}



# --- Tag stripping: mode=only (inline removal, preserve surrounding text) ---

class TestTagStripOnly:
    """Tags mode=only strips tags inline, preserving surrounding text."""

    def _filter(self, config, input_record, content, is_file_start=False):
        extractor = ObsidianExtractor(config, input_record)
        return extractor._filter_text_content(content, is_file_start, input_record.exclude_elements)

    def test_simple_tag(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'Hello #safety world\n')
        assert '#safety' not in result
        assert 'Hello' in result
        assert 'world' in result

    def test_nested_tag(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'Text #project/active here\n')
        assert '#project/active' not in result
        assert 'Text' in result
        assert 'here' in result

    def test_deeply_nested_tag(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'See #parent/child/grandchild end\n')
        assert '#parent/child/grandchild' not in result
        assert 'See' in result

    def test_tag_with_hyphen(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'Item #task-123 done\n')
        assert '#task-123' not in result
        assert 'Item' in result
        assert 'done' in result

    def test_multiple_tags_on_line(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'Tags #safety #performance #active\n')
        assert '#safety' not in result
        assert '#performance' not in result
        assert '#active' not in result
        assert 'Tags' in result

    def test_tag_at_start_of_line(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, '#safety is important\n')
        assert '#safety' not in result
        assert 'is important' in result

    def test_tag_at_end_of_line(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'This is tagged #safety\n')
        assert '#safety' not in result
        assert 'This is tagged' in result

    def test_heading_not_stripped(self, config, input_record_tags_only):
        content = '# Title\n## Section\n### Sub\n'
        result = self._filter(config, input_record_tags_only, content)
        assert '# Title\n' in result
        assert '## Section\n' in result

    def test_hex_3_digit_not_stripped(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'Color is #fff and #abc\n')
        assert '#fff' in result
        assert '#abc' in result

    def test_hex_6_digit_not_stripped(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'Color is #fafafa here\n')
        assert '#fafafa' in result

    def test_url_anchor_not_stripped(self, config, input_record_tags_only):
        content = 'Visit https://example.com/#section for more\n'
        result = self._filter(config, input_record_tags_only, content)
        assert 'https://example.com/#section' in result

    def test_tags_in_fenced_code_preserved(self, config, input_record_tags_only):
        content = 'Before #remove\n```\n#keep_this_tag\n```\nAfter #remove\n'
        result = self._filter(config, input_record_tags_only, content)
        assert '#keep_this_tag' in result
        assert '#remove' not in result

    def test_tags_in_inline_code_preserved(self, config, input_record_tags_only):
        content = 'Use `#safety` in your notes\n'
        result = self._filter(config, input_record_tags_only, content)
        assert '`#safety`' in result

    def test_mixed_inline_code_and_tags(self, config, input_record_tags_only):
        content = 'Strip #remove but keep `#keep` here #also_remove\n'
        result = self._filter(config, input_record_tags_only, content)
        assert '#remove' not in result
        assert '#also_remove' not in result
        assert '`#keep`' in result

    def test_no_double_spaces_after_removal(self, config, input_record_tags_only):
        result = self._filter(config, input_record_tags_only, 'Hello #tag world\n')
        assert '  ' not in result

    def test_newlines_preserved(self, config, input_record_tags_only):
        content = 'Line 1 #tag1\nLine 2 #tag2\nLine 3\n'
        result = self._filter(config, input_record_tags_only, content)
        lines = result.splitlines()
        assert len(lines) == 3

    def test_no_stripping_without_config(self, config, input_record_no_exclude):
        content = 'Hello #safety world\n'
        result = self._filter(config, input_record_no_exclude, content)
        assert '#safety' in result



# --- Tag stripping: mode=string (remove entire line if tag present) ---

class TestTagStripString:
    """Tags mode=string removes the entire line if it contains any tag."""

    def _filter(self, config, input_record, content, is_file_start=False):
        extractor = ObsidianExtractor(config, input_record)
        return extractor._filter_text_content(content, is_file_start, input_record.exclude_elements)

    def test_line_with_tag_removed(self, config, input_record_tags_string):
        result = self._filter(config, input_record_tags_string, 'Hello #safety world\n')
        assert result.strip() == ''

    def test_line_without_tag_preserved(self, config, input_record_tags_string):
        result = self._filter(config, input_record_tags_string, 'Hello world\n')
        assert 'Hello world' in result

    def test_multiple_lines_mixed(self, config, input_record_tags_string):
        content = 'Keep this line\nRemove #tag line\nAlso keep\n'
        result = self._filter(config, input_record_tags_string, content)
        assert 'Keep this line' in result
        assert 'Also keep' in result
        assert '#tag' not in result
        assert 'Remove' not in result

    def test_tag_in_code_span_does_not_trigger_removal(self, config, input_record_tags_string):
        content = 'Text with `#safe` only\n'
        result = self._filter(config, input_record_tags_string, content)
        assert 'Text with `#safe` only' in result

    def test_tag_outside_code_span_triggers_removal(self, config, input_record_tags_string):
        content = 'Text `#safe` but also #unsafe here\n'
        result = self._filter(config, input_record_tags_string, content)
        assert result.strip() == ''

    def test_fenced_code_block_preserved(self, config, input_record_tags_string):
        content = '```\n#tag_inside\n```\n'
        result = self._filter(config, input_record_tags_string, content)
        assert '#tag_inside' in result

    def test_heading_not_treated_as_tag(self, config, input_record_tags_string):
        content = '# Heading title\n'
        result = self._filter(config, input_record_tags_string, content)
        assert '# Heading title' in result


# --- Tag stripping: mode=string-on-start ---

class TestTagStripStringOnStart:
    """Tags mode=string-on-start removes line if tag is first non-ws, else strips inline."""

    def _filter(self, config, input_record, content, is_file_start=False):
        extractor = ObsidianExtractor(config, input_record)
        return extractor._filter_text_content(content, is_file_start, input_record.exclude_elements)

    def test_tag_at_start_removes_line(self, config, input_record_tags_string_on_start):
        result = self._filter(config, input_record_tags_string_on_start, '#safety is important\n')
        assert result.strip() == ''

    def test_tag_with_leading_whitespace_removes_line(self, config, input_record_tags_string_on_start):
        result = self._filter(config, input_record_tags_string_on_start, '   #safety rest of line\n')
        assert result.strip() == ''

    def test_tag_mid_line_strips_inline(self, config, input_record_tags_string_on_start):
        result = self._filter(config, input_record_tags_string_on_start, 'Important #safety note\n')
        assert '#safety' not in result
        assert 'Important' in result
        assert 'note' in result

    def test_no_tag_line_preserved(self, config, input_record_tags_string_on_start):
        result = self._filter(config, input_record_tags_string_on_start, 'Normal text here\n')
        assert 'Normal text here' in result

    def test_code_span_at_start_does_not_trigger(self, config, input_record_tags_string_on_start):
        content = '`#safety` is important\n'
        result = self._filter(config, input_record_tags_string_on_start, content)
        assert '`#safety`' in result
        assert 'is important' in result

    def test_multiple_tags_start_removes_line(self, config, input_record_tags_string_on_start):
        result = self._filter(config, input_record_tags_string_on_start, '#safety #performance\n')
        assert result.strip() == ''

    def test_heading_not_treated_as_tag(self, config, input_record_tags_string_on_start):
        content = '# Heading\n'
        result = self._filter(config, input_record_tags_string_on_start, content)
        assert '# Heading' in result

    def test_fenced_code_block_preserved(self, config, input_record_tags_string_on_start):
        content = '```\n#tag_inside\n```\n'
        result = self._filter(config, input_record_tags_string_on_start, content)
        assert '#tag_inside' in result



# --- Callouts mode tests ---

class TestCalloutsModes:
    """Tests for callouts with different removal modes."""

    def _filter(self, config, exclude, content, is_file_start=False):
        record = InputRecord(
            name='test', dir='.', record_base=config._base_dir, filepaths=[],
            driver='obsidian', default_atype='REQ', marker='REQ',
            exclude_elements=exclude,
        )
        extractor = ObsidianExtractor(config, record)
        return extractor._filter_text_content(content, is_file_start, record.exclude_elements)

    def test_callouts_string_on_start_removes_line(self, config):
        exclude = [ExcludeElementConfig(name='callouts', mode='string-on-start')]
        result = self._filter(config, exclude, '> quoted text\nKeep this\n')
        assert '>' not in result
        assert 'quoted text' not in result
        assert 'Keep this' in result

    def test_callouts_string_removes_line(self, config):
        exclude = [ExcludeElementConfig(name='callouts', mode='string')]
        result = self._filter(config, exclude, '> quoted text\nKeep this\n')
        assert 'quoted text' not in result
        assert 'Keep this' in result

    def test_callouts_only_strips_prefix(self, config):
        exclude = [ExcludeElementConfig(name='callouts', mode='only')]
        result = self._filter(config, exclude, '> quoted text\n')
        assert '>' not in result
        assert 'quoted text' in result

    def test_callouts_only_preserves_indentation(self, config):
        exclude = [ExcludeElementConfig(name='callouts', mode='only')]
        result = self._filter(config, exclude, '  > indented callout\n')
        assert '>' not in result
        assert '  indented callout' in result

    def test_callouts_in_code_block_preserved(self, config):
        exclude = [ExcludeElementConfig(name='callouts', mode='string-on-start')]
        content = '```\n> inside code\n```\n> outside code\n'
        result = self._filter(config, exclude, content)
        assert '> inside code' in result
        assert '> outside code' not in result


# --- Headings mode tests ---

class TestHeadingsModes:
    """Tests for headings with different removal modes."""

    def _filter(self, config, exclude, content, is_file_start=False):
        record = InputRecord(
            name='test', dir='.', record_base=config._base_dir, filepaths=[],
            driver='obsidian', default_atype='REQ', marker='REQ',
            exclude_elements=exclude,
        )
        extractor = ObsidianExtractor(config, record)
        return extractor._filter_text_content(content, is_file_start, record.exclude_elements)

    def test_headings_string_on_start_removes_line(self, config):
        exclude = [ExcludeElementConfig(name='headings', mode='string-on-start')]
        result = self._filter(config, exclude, '## Title\nContent here\n')
        assert 'Title' not in result
        assert 'Content here' in result

    def test_headings_string_removes_line(self, config):
        exclude = [ExcludeElementConfig(name='headings', mode='string')]
        result = self._filter(config, exclude, '## Title\nContent here\n')
        assert 'Title' not in result
        assert 'Content here' in result

    def test_headings_only_strips_prefix(self, config):
        exclude = [ExcludeElementConfig(name='headings', mode='only')]
        result = self._filter(config, exclude, '## Title\n')
        assert '##' not in result
        assert 'Title' in result

    def test_headings_only_preserves_indentation(self, config):
        exclude = [ExcludeElementConfig(name='headings', mode='only')]
        result = self._filter(config, exclude, '  ## Indented Heading\n')
        assert '##' not in result
        assert '  Indented Heading' in result

    def test_headings_in_code_block_preserved(self, config):
        exclude = [ExcludeElementConfig(name='headings', mode='string-on-start')]
        content = '```\n# comment\n```\n# real heading\n'
        result = self._filter(config, exclude, content)
        assert '# comment' in result
        assert '# real heading' not in result


# --- Horizontal rules mode tests ---

class TestHorizontalRulesModes:
    """Tests for horizontal_rules — all modes remove the line."""

    def _filter(self, config, exclude, content, is_file_start=False):
        record = InputRecord(
            name='test', dir='.', record_base=config._base_dir, filepaths=[],
            driver='obsidian', default_atype='REQ', marker='REQ',
            exclude_elements=exclude,
        )
        extractor = ObsidianExtractor(config, record)
        return extractor._filter_text_content(content, is_file_start, record.exclude_elements)

    def test_hr_only_removes_line(self, config):
        exclude = [ExcludeElementConfig(name='horizontal_rules', mode='only')]
        result = self._filter(config, exclude, '---\nText\n')
        assert '---' not in result
        assert 'Text' in result

    def test_hr_string_removes_line(self, config):
        exclude = [ExcludeElementConfig(name='horizontal_rules', mode='string')]
        result = self._filter(config, exclude, '***\nText\n')
        assert '***' not in result
        assert 'Text' in result

    def test_hr_string_on_start_removes_line(self, config):
        exclude = [ExcludeElementConfig(name='horizontal_rules', mode='string-on-start')]
        result = self._filter(config, exclude, '___\nText\n')
        assert '___' not in result
        assert 'Text' in result

    def test_hr_in_code_block_preserved(self, config):
        exclude = [ExcludeElementConfig(name='horizontal_rules', mode='string-on-start')]
        content = '```\n---\n```\n---\n'
        result = self._filter(config, exclude, content)
        lines = result.splitlines()
        assert '---' in lines  # inside code block



# --- Integration tests ---

class TestIntegration:
    """Integration tests verifying full extraction pipeline."""

    def test_text_blocks_stripped_artifact_untouched(self, config, input_record_tags_only, tmp_path):
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

        extractor = ObsidianExtractor(config, input_record_tags_only)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        for tb in text_blocks:
            assert '#safety' not in tb.content
            assert '#cleanup' not in tb.content

        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.fields['contents'].strip() == 'Requirement body with #performance tag.'

    def test_combined_callouts_only_and_tags_string_on_start(self, config, tmp_path):
        """Mixed modes: callouts=only strips prefix, tags=string-on-start removes/strips."""
        record = InputRecord(
            name='test', dir='.', record_base=tmp_path, filepaths=[],
            driver='obsidian', default_atype='REQ', marker='REQ',
            exclude_elements=[
                ExcludeElementConfig(name='callouts', mode='only'),
                ExcludeElementConfig(name='tags', mode='string-on-start'),
            ],
        )

        content = textwrap.dedent("""\
        > Important callout text.
        #remove_this_line entirely
        Keep this line with #inline_tag stripped.
        """)

        filepath = tmp_path / 'test.md'
        filepath.write_text(content, encoding='utf-8')

        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(filepath)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        combined = ''.join(tb.content for tb in text_blocks)

        # Callout prefix stripped, text kept
        assert '>' not in combined
        assert 'Important callout text' in combined
        # Line starting with tag removed
        assert 'remove_this_line' not in combined
        # Mid-line tag stripped
        assert '#inline_tag' not in combined
        assert 'Keep this line with' in combined

    def test_config_driven_structured_format(self, params, tmp_path):
        """Full config-driven test with structured exclude_elements in TOML."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(textwrap.dedent("""\
        base = "."

        [drivers.obsidian]
        exclude_elements = [{name = "tags", mode = "string-on-start"}]

        [[input]]
        name = "reqs"
        dir = "."
        driver = "obsidian"
        atype = "REQ"
        """), encoding='utf-8')

        md_path = tmp_path / 'REQ-001.md'
        md_path.write_text(textwrap.dedent("""\
        #internal should remove this line
        Notes with #draft stripped inline

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
        tag_elem = next(e for e in record.exclude_elements if e.name == 'tags')
        assert tag_elem.mode == 'string-on-start'

        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(md_path)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        combined = ''.join(tb.content for tb in text_blocks)

        # Line starting with tag removed entirely
        assert 'internal' not in combined
        # Mid-line tag stripped
        assert '#draft' not in combined
        assert 'Notes with' in combined

        # Artifact untouched
        artifact_blocks = [b for b in blocks if isinstance(b, ArtifactBlock)]
        assert len(artifact_blocks) == 1
        assert artifact_blocks[0].artifact.aid == 'REQ-001'

    def test_config_driven_multiple_modes(self, params, tmp_path):
        """Config with multiple elements at different modes."""
        cfg_path = tmp_path / 'config.toml'
        cfg_path.write_text(textwrap.dedent("""\
        base = "."

        [drivers.obsidian]
        exclude_elements = [
            {name = "headings", mode = "only"},
            {name = "callouts", mode = "string-on-start"},
            {name = "tags", mode = "string"},
        ]

        [[input]]
        name = "reqs"
        dir = "."
        driver = "obsidian"
        atype = "REQ"
        """), encoding='utf-8')

        md_path = tmp_path / 'REQ-001.md'
        md_path.write_text(textwrap.dedent("""\
        ## Section Title
        > Callout to remove
        Line with #tag should go
        Plain text stays

        [REQ]
        Content.
        [id] REQ-001
        ```yaml
        attrs:
          status: active
        ```
        """), encoding='utf-8')

        config = Config(params=params, config_filename=cfg_path)
        record = config.input_records()[0]

        extractor = ObsidianExtractor(config, record)
        blocks = extractor.extract_blocks_from_file(md_path)

        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        combined = ''.join(tb.content for tb in text_blocks)

        # Heading prefix stripped but text kept
        assert '##' not in combined
        assert 'Section Title' in combined
        # Callout line removed
        assert 'Callout to remove' not in combined
        # Tag line removed entirely (mode=string)
        assert '#tag' not in combined
        assert 'Line with' not in combined
        # Plain text preserved
        assert 'Plain text stays' in combined
