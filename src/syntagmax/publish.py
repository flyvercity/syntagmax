# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-06-20
# Description: Publish command - builds a block tree and renders to markdown.

import re
from typing import Optional
from syntagmax.blocks import BlockTree, InputBlock, FileRecord, TextBlock, ArtifactBlock, ErrorBlock, Block
from syntagmax.config import Config, InputRecord
from syntagmax.extract import EXTRACTORS
from syntagmax.artifact import Artifact
from syntagmax.publish_config import PublishConfig, TableSection, TextSection, MarkerRenderSection


def build_block_tree(config: Config) -> BlockTree:
    tree = BlockTree()

    for record in config.input_records():
        extractor = EXTRACTORS[record.driver](config, record, config.metamodel)
        sorted_paths = sorted(record.filepaths, key=lambda p: p.relative_to(record.record_base).as_posix())

        input_block = InputBlock(name=record.name)

        for filepath in sorted_paths:
            if not filepath.is_file():
                continue
            blocks = extractor.extract_blocks_from_file(filepath)
            if blocks:
                input_block.files.append(FileRecord(path=config.derive_path(filepath), blocks=blocks))

        tree.inputs.append(input_block)

    return tree


def strip_numeric_prefix(header_text: str) -> str:
    # Strip numeric prefixes like "1.2.3 Title" -> "Title"
    m = re.match(r'^\s*(?:[0-9]+(?:\.[0-9]+)*\s*[-.]?|[0-9]+\s+)(.*)$', header_text)
    if m:
        return m.group(1).strip()
    return header_text


def process_heading_line(line: str, start_level: int, remove_prefixes: bool) -> str:
    m = re.match(r'^(#{1,6})(\s+)(.*)$', line)
    if m:
        hashes, space, content = m.groups()
        if remove_prefixes:
            content = strip_numeric_prefix(content)
        offset = start_level - 1
        new_level = min(6, len(hashes) + offset)
        return f'{"#" * new_level}{space}{content}'
    return line


def adjust_text_headings_and_prefixes(text: str, start_level: int, remove_prefixes: bool) -> str:
    lines = []
    for line in text.splitlines():
        processed = process_heading_line(line, start_level, remove_prefixes)
        lines.append(processed)

    result = '\n'.join(lines)
    if text.endswith('\n') and not result.endswith('\n') and result:
        result += '\n'
    return result


def get_artifact_field_value(artifact: Artifact, field_name: str) -> Optional[str]:
    target_key = field_name.lower()
    if target_key == 'id':
        return artifact.aid

    # Case-insensitive lookup in fields
    for k, v in artifact.fields.items():
        if k.lower() == target_key:
            if isinstance(v, list):
                joined = ', '.join(str(x) for x in v if str(x).strip())
                return joined if joined.strip() else None
            val = str(v)
            return val if val.strip() else None
    return None


def render_artifact_fallback(artifact: Artifact, start_level: int) -> str:
    parts = []
    level = min(6, start_level + 2)
    parts.append(f'{"#" * level} {artifact.aid}\n\n')

    contents = get_artifact_field_value(artifact, 'contents')
    if contents:
        parts.append(f'{contents.strip()}\n\n')

    # Metadata table - skip id and contents
    fields = {k: v for k, v in artifact.fields.items() if k.lower() not in ('id', 'contents')}
    if fields:
        sorted_keys = sorted(fields.keys())
        parts.append('| Field | Value |\n|-------|-------|\n')
        for k in sorted_keys:
            v = fields[k]
            display = ', '.join(str(i) for i in v) if isinstance(v, list) else str(v)
            parts.append(f'| {k} | {display} |\n')
        parts.append('\n')

    return ''.join(parts)


def render_block(block: Block, pub_config: PublishConfig) -> str:
    if isinstance(block, ErrorBlock):
        return f'> **Publish error:** {block.message}\n\n'

    if isinstance(block, TextBlock):
        marker = block.marker
        if marker is not None:
            # Look up marker case-insensitively
            render_sections = None
            for k, v in pub_config.render.items():
                if k.upper() == marker.upper():
                    render_sections = v
                    break

            if render_sections:
                parts = []
                for sec in render_sections:
                    if isinstance(sec, MarkerRenderSection):
                        content = block.content.strip()
                        if sec.mode == 'block':
                            parts.append(f'**{sec.alias}**\n\n{content}\n\n')
                        elif sec.mode == 'inline':
                            parts.append(f'**{sec.alias}**: {content}\n\n')
                return ''.join(parts)
            else:
                # If marker configured but not in render, fall back to plain text
                return adjust_text_headings_and_prefixes(
                    block.content,
                    pub_config.start_level,
                    pub_config.remove_numeric_prefixes_in_headers,
                )
        else:
            # Unmarked text block
            if not pub_config.include_plain_text:
                return ''
            return adjust_text_headings_and_prefixes(
                block.content,
                pub_config.start_level,
                pub_config.remove_numeric_prefixes_in_headers,
            )

    if isinstance(block, ArtifactBlock):
        a = block.artifact
        render_sections = None
        for k, v in pub_config.render.items():
            if k.upper() == a.atype.upper():
                render_sections = v
                break

        if not render_sections:
            return render_artifact_fallback(a, pub_config.start_level)

        parts = []
        for sec in render_sections:
            if isinstance(sec, TableSection):
                rows = []
                for attr_dict in sec.attributes:
                    attr_name = list(attr_dict.keys())[0]
                    attr_render = attr_dict[attr_name]
                    val = get_artifact_field_value(a, attr_name)
                    if val:
                        rows.append((attr_render.alias, val))
                if rows:
                    parts.append('|           |       |\n|-----------|-------|\n')
                    for alias, val in rows:
                        parts.append(f'| {alias} | {val} |\n')
                    parts.append('\n')
            elif isinstance(sec, TextSection):
                for attr_dict in sec.attributes:
                    attr_name = list(attr_dict.keys())[0]
                    attr_render = attr_dict[attr_name]
                    val = get_artifact_field_value(a, attr_name)
                    if val:
                        processed_val = adjust_text_headings_and_prefixes(
                            val,
                            pub_config.start_level,
                            pub_config.remove_numeric_prefixes_in_headers,
                        ).strip()
                        if sec.mode == 'block':
                            parts.append(f'**{attr_render.alias}**\n\n{processed_val}\n\n')
                        elif sec.mode == 'inline':
                            parts.append(f'**{attr_render.alias}**: {processed_val}\n\n')

        return ''.join(parts)

    return ''


def decompose_file_path(file_path: str, record_dir: str) -> list[str]:
    """Decompose FileRecord.path into heading components.

    Strips the record's dir prefix and file extension.
    Returns list of components: [dir1, dir2, ..., file_stem]
    """
    from pathlib import PurePosixPath

    parts = PurePosixPath(file_path).parts
    dir_parts = PurePosixPath(record_dir).parts

    # Strip leading components matching record dir
    if parts[:len(dir_parts)] == dir_parts:
        parts = parts[len(dir_parts):]

    # Strip extension from last component (filename)
    if parts:
        parts = list(parts)
        parts[-1] = PurePosixPath(parts[-1]).stem

    return list(parts)


def render_block_tree(tree: BlockTree, config: Optional[Config] = None, multi_record: bool = True) -> str:
    parts: list[str] = []

    record_map: dict[str, InputRecord] = {}
    if config:
        for r in config.input_records():
            record_map[r.name] = r

    for input_block in tree.inputs:
        pub_config = PublishConfig()
        record_dir = ''
        if config and input_block.name in record_map:
            pub_config = config.load_publish_config(record_map[input_block.name])
            record_dir = record_map[input_block.name].dir

        # Emit record name heading only in multi_record mode
        if multi_record:
            record_heading = input_block.name
            if pub_config.remove_numeric_prefixes_in_headers:
                record_heading = strip_numeric_prefix(record_heading)
            level = min(6, pub_config.start_level)
            parts.append(f'{"#" * level} {record_heading}\n\n')

        # Base level for path headings
        path_base_level = pub_config.start_level + 1 if multi_record else pub_config.start_level

        # Track emitted path components to avoid duplicates
        last_components: list[str] = []

        for file_record in input_block.files:
            # Decompose path into heading components
            components = decompose_file_path(file_record.path, record_dir)

            if components:
                # Find longest common prefix with previous file
                common_len = 0
                for i, (a, b) in enumerate(zip(last_components, components)):
                    if a == b:
                        common_len = i + 1
                    else:
                        break

                # Emit headings only for new components
                for i in range(common_len, len(components)):
                    heading_text = components[i]
                    if pub_config.remove_numeric_prefixes_in_headers:
                        heading_text = strip_numeric_prefix(heading_text)
                    level = min(6, path_base_level + i)
                    parts.append(f'{"#" * level} {heading_text}\n\n')

                last_components = components

            for block in file_record.blocks:
                block_content = render_block(block, pub_config)
                if block_content:
                    # Ensure each block ends with exactly \n\n for inter-block spacing
                    stripped = block_content.rstrip('\n')
                    if stripped:
                        parts.append(stripped + '\n\n')

    # Join and collapse excessive blank lines (3+ newlines → 2)
    result = ''.join(parts)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result
