# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-25
# Description: Task generation from impact analysis results.

import logging as lg
from dataclasses import dataclass
from pathlib import Path

from benedict import benedict
from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from ruamel.yaml import YAML

from syntagmax.artifact import Artifact, ArtifactMap
from syntagmax.config import Config, InputRecord


IMPLICIT_TASK_METAMODEL = {
    'attributes': {
        'id': [{'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}}],
        'contents': [{'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}}],
        'status': [{'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'enum', 'values': ['open', 'closed']}}],
    }
}


@dataclass
class TaskData:
    task_id: str
    task_atype: str
    child_aid: str
    child_atype: str
    child_record_name: str
    child_file_path: str
    child_revision_short: str | None
    child_revision_long: str | None
    parent_aid: str
    parent_atype: str
    parent_record_name: str
    parent_file_path: str
    parent_revision_short: str | None
    parent_revision_long: str | None
    nominal_revision: str
    actual_revision: str


def generate_task_id(child_aid: str, parent_aid: str) -> str:
    """Generate a deterministic task ID from a child/parent artifact pair."""
    return f'TASK-IMPACT-{child_aid}-{parent_aid}'


def sanitize_filename(name: str) -> str:
    """Replace filesystem-unsafe characters with hyphens."""
    unsafe = '/\\:*?"<>|'
    for ch in unsafe:
        name = name.replace(ch, '-')
    return name


def render_task_file(template_env: Environment, template_name: str, task_data: TaskData) -> str:
    """Render a task file from a Jinja2 template."""
    template = template_env.get_template(template_name)
    return template.render(task=task_data)


def scan_existing_tasks(tasks_dir: Path) -> dict[str, dict]:
    """Scan task files and return {task_id: {status, parent_revision, child_revision}} mapping."""
    existing: dict[str, dict] = {}
    if not tasks_dir.exists():
        return existing
    for md_file in tasks_dir.glob('*.md'):
        content = md_file.read_text(encoding='utf-8')
        frontmatter = _parse_frontmatter(content)
        if frontmatter and 'id' in frontmatter:
            existing[frontmatter['id']] = {
                'status': frontmatter.get('status', 'open'),
                'parent_revision': frontmatter.get('parent_revision', ''),
                'child_revision': frontmatter.get('child_revision', ''),
            }
    return existing


def should_generate_task(task_id: str, current_parent_rev: str, current_child_rev: str, existing_tasks: dict[str, dict]) -> bool:
    """Determine if a task should be generated/regenerated."""
    if task_id not in existing_tasks:
        return True
    task_info = existing_tasks[task_id]
    # Regenerate if revisions have changed
    if task_info.get('parent_revision') != current_parent_rev:
        return True
    if task_info.get('child_revision') != current_child_rev:
        return True
    # Revisions match - skip regardless of status
    return False


def inject_task_metamodel(metamodel: dict, impact_config) -> None:
    """Inject implicit TASK metamodel for any task atypes not already defined."""
    if not impact_config.tasks_enabled:
        return
    artifacts = metamodel.setdefault('artifacts', {})
    # Collect all task atypes that might be used
    task_atypes = set(impact_config.task_atype_map.values()) | {'TASK'}
    for atype in task_atypes:
        if atype not in artifacts:
            artifacts[atype] = IMPLICIT_TASK_METAMODEL


def generate_tasks(config: Config, artifacts: ArtifactMap, errors: list[str], impact_data: benedict) -> dict:
    """Generate task files from impact analysis results. Returns summary dict."""
    if not config.impact.tasks_enabled:
        return {'created': 0, 'skipped': 0}

    tasks_dir = config.tasks_dir()
    tasks_dir.mkdir(parents=True, exist_ok=True)

    existing_tasks = scan_existing_tasks(tasks_dir)
    suspicious_links = impact_data.get('suspicious_links', [])

    created = 0
    skipped = 0

    for link in suspicious_links:
        child = artifacts.get(link['artifact_aid'])
        parent = artifacts.get(link['parent_aid'])
        if not child or not parent:
            continue

        task_id = generate_task_id(link['artifact_aid'], link['parent_aid'])

        current_parent_rev = parent.latest_revision.hash_short if parent.latest_revision else ''
        current_child_rev = child.latest_revision.hash_short if child.latest_revision else ''

        if not should_generate_task(task_id, current_parent_rev, current_child_rev, existing_tasks):
            skipped += 1
            continue

        atype_key = f'{link["parent_atype"]}/{link["artifact_atype"]}'
        task_atype = config.impact.task_atype_map.get(atype_key, 'TASK')

        # Resolve template per child's input record (mirrors publish resolution)
        template_env, template_name = _build_template_env(config, child.record)

        task_data = _build_task_data(task_id, task_atype, child, parent, link)
        content = render_task_file(template_env, template_name, task_data)

        safe_filename = sanitize_filename(f'{task_id}.md')
        task_file = tasks_dir / safe_filename
        task_file.write_text(content, encoding='utf-8')
        created += 1

    lg.info(f'Task generation: {created} created, {skipped} skipped')
    return {'created': created, 'skipped': skipped}


def _build_template_env(config: Config, record: InputRecord | None = None) -> tuple[Environment, str]:
    """Build Jinja2 environment and resolve template name for task rendering.

    Resolution order: record-level -> global -> built-in (mirrors publish pattern).
    """
    template_dir, template_name = config.resolve_task_template(record)

    loaders = []
    if template_dir and template_dir.exists():
        loaders.append(FileSystemLoader(str(template_dir)))

    # Always include built-in resources as final fallback
    resources_dir = Path(__file__).parent / 'resources'
    loaders.append(FileSystemLoader(str(resources_dir)))

    env = Environment(loader=ChoiceLoader(loaders))
    return env, template_name


def _build_task_data(task_id: str, task_atype: str, child: Artifact, parent: Artifact, link: dict) -> TaskData:
    """Build TaskData from artifact objects and suspicious link info."""
    return TaskData(
        task_id=task_id,
        task_atype=task_atype,
        child_aid=child.aid,
        child_atype=child.atype,
        child_record_name=child.record.name if child.record else '',
        child_file_path=child.location.filepath() if child.location else '',
        child_revision_short=child.latest_revision.hash_short if child.latest_revision else None,
        child_revision_long=child.latest_revision.hash_long if child.latest_revision else None,
        parent_aid=parent.aid,
        parent_atype=parent.atype,
        parent_record_name=parent.record.name if parent.record else '',
        parent_file_path=parent.location.filepath() if parent.location else '',
        parent_revision_short=parent.latest_revision.hash_short if parent.latest_revision else None,
        parent_revision_long=parent.latest_revision.hash_long if parent.latest_revision else None,
        nominal_revision=link.get('nominal_revision', ''),
        actual_revision=link.get('actual_revision', ''),
    )


def _parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith('---'):
        return None
    end = content.find('---', 3)
    if end == -1:
        return None
    yaml_str = content[3:end].strip()
    yaml = YAML(typ='safe')
    try:
        return yaml.load(yaml_str)
    except Exception:
        return None
