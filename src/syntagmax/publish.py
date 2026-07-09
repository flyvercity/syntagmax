# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-06-20
# Description: Publish command - builds a block tree and renders to markdown.

import re
from typing import Optional
from syntagmax.blocks import BlockTree, InputBlock, FileRecord, TextBlock, ArtifactBlock, ErrorBlock, Block
from syntagmax.config import Config, InputRecord
from syntagmax.extract import EXTRACTORS
from syntagmax.artifact import Artifact, FileLocation
from syntagmax.publish_config import PublishConfig, TableSection, TextSection, MarkerRenderSection
from syntagmax.publish_context import (
    RenderContext, ImageManifest, IMAGE_EXTENSIONS,
    resolve_image_to_manifest, _is_remote_url,
)


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


_OBSIDIAN_IMAGE_RE = re.compile(r'!\[\[([^\]]+)\]\]')
_STANDARD_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
_FENCE_RE = re.compile(r'^```', re.MULTILINE)


def rewrite_image_references(content: str, context: RenderContext) -> str:
    """Rewrite image references in text content to point to the images/ output directory.

    Supports Obsidian wiki-link syntax (![[filename.ext]]) and standard markdown
    syntax (![alt](path)). References inside fenced code blocks are preserved.
    Remote URLs are left unchanged without warning.
    """
    # Split content into fenced and non-fenced segments
    fence_positions = [m.start() for m in _FENCE_RE.finditer(content)]
    if len(fence_positions) < 2:
        # No complete fenced blocks, process entire content
        return _rewrite_images_in_segment(content, context)

    # Process segments: alternate between outside-fence and inside-fence
    result_parts: list[str] = []
    pos = 0
    in_fence = False
    for fence_pos in fence_positions:
        if not in_fence:
            # Process text before this fence opening
            segment = content[pos:fence_pos]
            result_parts.append(_rewrite_images_in_segment(segment, context))
            pos = fence_pos
            in_fence = True
        else:
            # End of fenced block — include the fenced content verbatim
            # Find the end of this line (the closing ```)
            line_end = content.find('\n', fence_pos)
            if line_end == -1:
                line_end = len(content)
            else:
                line_end += 1
            result_parts.append(content[pos:line_end])
            pos = line_end
            in_fence = False

    # Remaining content after last fence marker
    if pos < len(content):
        if in_fence:
            # Still inside a fenced block (unclosed) — leave verbatim
            result_parts.append(content[pos:])
        else:
            result_parts.append(_rewrite_images_in_segment(content[pos:], context))

    return ''.join(result_parts)


def _rewrite_images_in_segment(segment: str, context: RenderContext) -> str:
    """Rewrite image references in a non-fenced text segment."""
    # First pass: Obsidian wiki-link images ![[filename|alt]]
    segment = _OBSIDIAN_IMAGE_RE.sub(
        lambda m: _replace_obsidian_image(m, context), segment
    )
    # Second pass: standard markdown images ![alt](path)
    segment = _STANDARD_IMAGE_RE.sub(
        lambda m: _replace_standard_image(m, context), segment
    )
    return segment


def _replace_obsidian_image(match: re.Match, context: RenderContext) -> str:
    """Replace an Obsidian ![[filename|alt]] reference."""
    raw = match.group(1)
    # Parse optional alt text after pipe
    if '|' in raw:
        filename, alt = raw.split('|', 1)
        filename = filename.strip()
        alt = alt.strip()
    else:
        filename = raw.strip()
        alt = filename.rsplit('.', 1)[0] if '.' in filename else filename

    # Check extension
    from pathlib import PurePosixPath
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        return match.group(0)  # Not an image, leave unchanged

    target = resolve_image_to_manifest(filename, context, is_obsidian=True)
    if target is None:
        return match.group(0)  # Unresolvable, leave unchanged

    return f'![{alt}]({target})'


def _replace_standard_image(match: re.Match, context: RenderContext) -> str:
    """Replace a standard ![alt](path) reference."""
    alt = match.group(1)
    path = match.group(2)

    # Skip remote URLs
    if _is_remote_url(path):
        return match.group(0)

    # Skip already-rewritten paths (from Obsidian pass)
    if path.startswith('images/'):
        return match.group(0)

    # Check extension
    from pathlib import PurePosixPath
    ext = PurePosixPath(path.split('?')[0]).suffix.lower()  # strip query params
    if ext not in IMAGE_EXTENSIONS:
        return match.group(0)  # Not an image, leave unchanged

    target = resolve_image_to_manifest(path, context, is_obsidian=False)
    if target is None:
        return match.group(0)  # Unresolvable, leave unchanged

    return f'![{alt}]({target})'


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


def render_artifact_fallback(artifact: Artifact, content_level: int) -> str:
    """Render an artifact using fallback formatting (no custom render config).

    Args:
        artifact: The artifact to render.
        content_level: The heading level at which the artifact ID should appear.
            This accounts for the file's hierarchical position in the document.
    """
    parts = []
    level = min(6, content_level)
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


def render_block(block: Block, pub_config: PublishConfig, context: RenderContext | None = None, content_level: int | None = None) -> str:
    """Render a single block to Markdown.

    Args:
        block: The block to render.
        pub_config: Publishing configuration.
        context: Optional render context for image rewriting.
        content_level: The heading level at which a source H1 should appear in output.
            Accounts for the file's hierarchical position. When None, defaults to
            pub_config.start_level (backward compatibility for direct callers).
    """
    effective_level = content_level if content_level is not None else pub_config.start_level

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
                        if context:
                            content = rewrite_image_references(content, context)
                        if sec.mode == 'block':
                            parts.append(f'**{sec.alias}**\n\n{content}\n\n')
                        elif sec.mode == 'inline':
                            parts.append(f'**{sec.alias}**: {content}\n\n')
                return ''.join(parts)
            else:
                # If marker configured but not in render, fall back to plain text
                content = adjust_text_headings_and_prefixes(
                    block.content,
                    effective_level,
                    pub_config.remove_numeric_prefixes_in_headers,
                )
                if context:
                    content = rewrite_image_references(content, context)
                return content
        else:
            # Unmarked text block
            if not pub_config.include_plain_text:
                return ''
            content = adjust_text_headings_and_prefixes(
                block.content,
                effective_level,
                pub_config.remove_numeric_prefixes_in_headers,
            )
            if context:
                content = rewrite_image_references(content, context)
            return content

    if isinstance(block, ArtifactBlock):
        a = block.artifact

        # Check if this is a sidecar image artifact — emit image embed
        image_embed = ''
        if context and isinstance(a.location, FileLocation):
            from pathlib import PurePosixPath
            ext = PurePosixPath(a.location.loc_file).suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                base_dir = context.config.base_dir()
                source = (base_dir / a.location.loc_file).resolve()
                from syntagmax.publish_context import _is_within_base_dir
                if _is_within_base_dir(source, base_dir):
                    target = context.manifest.add(source, base_dir)
                    alt_text = get_artifact_field_value(a, 'title') or a.aid
                    image_embed = f'![{alt_text}]({target})\n\n'

        render_sections = None
        for k, v in pub_config.render.items():
            if k.upper() == a.atype.upper():
                render_sections = v
                break

        if not render_sections:
            return image_embed + render_artifact_fallback(a, effective_level)

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
                            effective_level,
                            pub_config.remove_numeric_prefixes_in_headers,
                        ).strip()
                        if sec.mode == 'block':
                            parts.append(f'**{attr_render.alias}**\n\n{processed_val}\n\n')
                        elif sec.mode == 'inline':
                            parts.append(f'**{attr_render.alias}**: {processed_val}\n\n')

        return image_embed + ''.join(parts)

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


def render_block_tree(tree: BlockTree, config: Optional[Config] = None, multi_record: bool = True) -> tuple[str, ImageManifest]:
    parts: list[str] = []

    context: RenderContext | None = None
    if config:
        context = RenderContext(config=config)

    manifest = context.manifest if context else ImageManifest()

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
            if context:
                context.source_file_path = file_record.path

            # Decompose path into heading components
            components = decompose_file_path(file_record.path, record_dir)

            # Detect content files: last component matches contents_marker (case-insensitive)
            # Apply numeric prefix stripping before comparison when enabled,
            # since the user sees/names files by their effective (stripped) name.
            last_stem = components[-1] if components else ''
            if pub_config.remove_numeric_prefixes_in_headers:
                last_stem = strip_numeric_prefix(last_stem)
            is_content_file = (
                bool(components)
                and last_stem.lower() == pub_config.contents_marker.lower()
            )

            if components:
                if is_content_file:
                    # Content file: emit headings for directory components only (not the file stem)
                    dir_components = components[:-1]

                    # Find longest common prefix with previous file (compare dir parts only)
                    common_len = 0
                    for i, (a, b) in enumerate(zip(last_components, dir_components)):
                        if a == b:
                            common_len = i + 1
                        else:
                            break

                    # Emit headings only for new directory components
                    for i in range(common_len, len(dir_components)):
                        heading_text = dir_components[i]
                        if pub_config.remove_numeric_prefixes_in_headers:
                            heading_text = strip_numeric_prefix(heading_text)
                        level = min(6, path_base_level + i)
                        parts.append(f'{"#" * level} {heading_text}\n\n')

                    # Update last_components to directory parts only
                    last_components = dir_components
                else:
                    # Normal file: emit headings for all new components (dirs + file stem)
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

            # Content level calculation:
            # - Normal file: one level deeper than the file's own path heading
            # - Content file: at the directory's body level (same depth as file heading would be)
            if is_content_file:
                content_level = min(6, path_base_level + len(components) - 1) if components else path_base_level
            else:
                content_level = min(6, path_base_level + len(components)) if components else path_base_level

            for block in file_record.blocks:
                block_content = render_block(block, pub_config, context, content_level=content_level)
                if block_content:
                    # Ensure each block ends with exactly \n\n for inter-block spacing
                    stripped = block_content.rstrip('\n')
                    if stripped:
                        parts.append(stripped + '\n\n')

    # Join and collapse excessive blank lines (3+ newlines → 2)
    result = ''.join(parts)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result, manifest
