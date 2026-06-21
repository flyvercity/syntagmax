# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-06-20
# Description: Publish command - builds a block tree and renders to markdown.

from syntagmax.blocks import BlockTree, InputBlock, FileRecord, TextBlock, ArtifactBlock, ErrorBlock
from syntagmax.config import Config
from syntagmax.extract import EXTRACTORS


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


def render_block_tree(tree: BlockTree) -> str:
    parts: list[str] = []

    for input_block in tree.inputs:
        parts.append(f'## {input_block.name}\n\n')

        for file_record in input_block.files:
            for block in file_record.blocks:
                if isinstance(block, TextBlock):
                    parts.append(block.content)
                elif isinstance(block, ErrorBlock):
                    parts.append(f'> **Publish error:** {block.message}\n\n')
                elif isinstance(block, ArtifactBlock):
                    a = block.artifact
                    parts.append(f'### {a.aid}\n\n')
                    parts.append(f'{a.contents()}\n\n')

                    # Metadata table - skip id and contents
                    fields = {k: v for k, v in a.fields.items() if k not in ('id', 'contents')}
                    if fields:
                        parts.append('| Field | Value |\n|-------|-------|\n')
                        for k, v in fields.items():
                            display = ', '.join(str(i) for i in v) if isinstance(v, list) else str(v)
                            parts.append(f'| {k} | {display} |\n')
                        parts.append('\n')

    return ''.join(parts)
