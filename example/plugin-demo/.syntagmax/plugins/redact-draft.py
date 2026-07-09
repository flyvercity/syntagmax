"""Plugin: redact-draft

Demonstrates the filter_block hook.
Omits any ArtifactBlock whose 'status' field is 'draft'.
"""

from syntagmax.blocks import ArtifactBlock, Block, FileRecord


def filter_block(block: Block, file_record: FileRecord, config, params: dict) -> Block | None:
    """Return None for draft artifacts to omit them from published output."""
    if isinstance(block, ArtifactBlock):
        status = block.artifact.fields.get('status', '')
        if status == 'draft':
            return None
    return block
