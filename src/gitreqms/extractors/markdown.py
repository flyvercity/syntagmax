# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Extracts artifacts from markdown files.

import yaml
from typing import Generator


def extract_from_markdown(markdown: str) -> list[str], str:
    lines = markdown.split('\n')

    for block in _next_code_block(lines):
        block_yaml = yaml.safe_load('\n'.join(block))
        
        metadata = block_yaml.get('gitreqms', {})

        if not metadata:
            continue

        

def _next_code_block(lines: list[str]) -> Generator[list[str]]:
    block: list[str] = []
    capture = False

    for line in lines:
        if line.startswith('```yaml'):
            capture = True
            continue
            
        if line.startswith('```'):
            capture = False
            yield block
            block = []

        if capture:
            block.append(line)
