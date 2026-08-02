# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: AI prompt rendering utilities for Syntagmax.

import importlib.resources
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from syntagmax.errors import FatalError

lg = logging.getLogger(__name__)


def load_agent_registry(config) -> dict:
    """Load agent definitions from package resources or custom file."""
    if config.ai.agents_file:
        custom_path = config.root_dir() / config.ai.agents_file
        if not custom_path.exists():
            raise FatalError(f'Custom agents file not found: {custom_path}')
        lg.info(f'Loading custom agent registry from {custom_path}')
        data = yaml.safe_load(custom_path.read_text(encoding='utf-8'))
    else:
        resource_path = importlib.resources.files('syntagmax.resources').joinpath('agents.yaml')
        lg.debug('Loading default agent registry from package resources')
        data = yaml.safe_load(resource_path.read_text(encoding='utf-8'))

    if not data or 'agents' not in data:
        raise FatalError('Invalid agent registry: missing "agents" key')

    return data['agents']


def resolve_agent(registry: dict, agent_name: str) -> dict:
    """Look up agent by name, raise FatalError if not found."""
    if agent_name not in registry:
        available = ', '.join(sorted(registry.keys()))
        raise FatalError(f"Unknown agent '{agent_name}'. Available agents: {available}")
    return registry[agent_name]


def render_verify_prompt(
    config,
    task_file_path: str,
    parent_aid: str,
    parent_atype: str,
    parent_file_path: str,
    parent_repo_path: str,
    parent_revision: str,
    child_aid: str,
    child_atype: str,
    child_file_path: str,
    child_repo_path: str,
    agent_name: str,
) -> str:
    """Render the impact verification prompt."""
    from datetime import datetime, timezone

    resources_dir = str(importlib.resources.files('syntagmax.resources'))
    env = Environment(loader=FileSystemLoader(resources_dir), keep_trailing_newline=True)
    template = env.get_template('ai-verify-impact.j2')

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    return template.render(
        persona=config.ai.persona,
        task_file_path=task_file_path,
        parent_aid=parent_aid,
        parent_atype=parent_atype,
        parent_file_path=parent_file_path,
        parent_repo_path=parent_repo_path,
        parent_revision=parent_revision,
        child_aid=child_aid,
        child_atype=child_atype,
        child_file_path=child_file_path,
        child_repo_path=child_repo_path,
        agent_name=agent_name,
        timestamp=timestamp,
    )



_FRONTMATTER_RE = re.compile(
    r'^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(.*))?$',
    re.DOTALL,
)


def _parse_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from markdown content."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        return None
    return data


def validate_task_post_edit(task_path: Path, original_id: str) -> tuple[bool, str]:
    """Validate task file integrity after agent edit.

    Returns (is_valid, message).
    """
    try:
        content = task_path.read_text(encoding='utf-8')
    except Exception as e:
        return False, f'Cannot read task file after edit: {e}'

    frontmatter = _parse_frontmatter(content)

    if frontmatter is None:
        return False, 'Task file has no valid frontmatter after edit'

    if frontmatter.get('id') != original_id:
        return False, f'Task ID was modified (expected {original_id})'

    status = frontmatter.get('status')
    if status not in ('open', 'closed'):
        return False, f'Invalid status "{status}" (must be open or closed)'

    if '## Verification Report' not in content:
        return False, 'No "## Verification Report" section found'

    return True, 'valid'


@dataclass
class ImpactTaskInfo:
    """Parsed metadata from an impact task file."""
    task_id: str
    status: str
    parent_aid: str
    parent_atype: str
    parent_file_path: str
    parent_revision: str
    child_aid: str
    child_atype: str
    child_file_path: str


_FIELD_RE = re.compile(r'^- \*\*(.+?):\*\*\s*(.+)$', re.MULTILINE)


def parse_impact_task(task_path: Path) -> ImpactTaskInfo:
    """Parse an impact task file and extract all metadata.

    Raises FatalError if the file cannot be parsed or is missing required fields.
    """
    content = task_path.read_text(encoding='utf-8')
    frontmatter = _parse_frontmatter(content)

    if frontmatter is None:
        raise FatalError(f'Task file has no valid frontmatter: {task_path}')

    task_id = frontmatter.get('id', '')
    status = frontmatter.get('status', '')
    parent_revision = frontmatter.get('parent_revision', '')

    # Parse structured sections from markdown body
    # Split into Parent and Child sections
    parent_fields = {}
    child_fields = {}

    # Find Parent section
    parent_match = re.search(r'## Parent \(Updated\)\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if parent_match:
        for m in _FIELD_RE.finditer(parent_match.group(1)):
            parent_fields[m.group(1)] = m.group(2).strip()

    # Find Child section
    child_match = re.search(r'## Child \(Outdated\)\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if child_match:
        for m in _FIELD_RE.finditer(child_match.group(1)):
            child_fields[m.group(1)] = m.group(2).strip()

    # Validate required fields
    missing = []
    if 'ID' not in parent_fields:
        missing.append('Parent ID')
    if 'Type' not in parent_fields:
        missing.append('Parent Type')
    if 'File' not in parent_fields:
        missing.append('Parent File')
    if 'ID' not in child_fields:
        missing.append('Child ID')
    if 'Type' not in child_fields:
        missing.append('Child Type')
    if 'File' not in child_fields:
        missing.append('Child File')

    if missing:
        raise FatalError(f'Impact task missing required fields: {", ".join(missing)}')

    return ImpactTaskInfo(
        task_id=task_id,
        status=status,
        parent_aid=parent_fields['ID'],
        parent_atype=parent_fields['Type'],
        parent_file_path=parent_fields['File'],
        parent_revision=parent_revision,
        child_aid=child_fields['ID'],
        child_atype=child_fields['Type'],
        child_file_path=child_fields['File'],
    )


def invoke_agent(agent_config: dict, prompt: str, working_dir: Path) -> int:
    """Invoke the agent interactively, returning exit code.

    The agent command is a pattern string with a {prompt} placeholder.
    The prompt is written to a temporary file and {prompt} is replaced
    with the file path.
    """
    import subprocess
    import tempfile
    import shlex
    import os

    command_pattern = agent_config['command']

    lg.debug(f'Invoking agent: {command_pattern}')

    prompt_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(prompt)
            prompt_path = f.name

        command_str = command_pattern.replace('{prompt}', prompt_path)
        cmd_parts = shlex.split(command_str)
        lg.debug(f'Agent command: {cmd_parts}')

        result = subprocess.run(
            cmd_parts,
            cwd=working_dir,
        )
        return result.returncode
    except FileNotFoundError:
        executable = shlex.split(command_pattern)[0]
        raise FatalError(f"Agent executable '{executable}' not found on PATH.")
    finally:
        if prompt_path and os.path.exists(prompt_path):
            os.unlink(prompt_path)
