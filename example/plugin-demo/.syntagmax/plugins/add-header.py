"""Plugin: add-header

Demonstrates the transform_markdown hook.
Prepends a document header with title and version from params.
"""


def transform_markdown(markdown: str, config, params: dict) -> str:
    title = params.get('title', 'Untitled')
    version = params.get('version', '')

    header_parts = [f'# {title}\n']
    if version:
        header_parts.append(f'\n**Version:** {version}\n')
    header_parts.append('\n---\n\n')

    return ''.join(header_parts) + markdown
