# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-08-02
# Description: CLI commands for AI-assisted operations.

import logging as lg
import sys
from pathlib import Path

import click
import git

import syntagmax.utils as u
from syntagmax.config import Config, Params
from syntagmax.ai import (
    ImpactTaskInfo,
    invoke_agent,
    load_agent_registry,
    parse_impact_task,
    render_verify_prompt,
    resolve_agent,
    validate_task_post_edit,
)


@click.group(help='AI-assisted commands')
def ai():
    pass


@ai.command(help='Verify an impact task using an AI agent')
@click.argument('task_file', type=click.Path(exists=True))
@click.option('--agent', default=None, help='Override the default agent')
@click.option('-f', '--config-file', type=click.Path(), default='.syntagmax/config.toml')
@click.pass_obj
def verify(obj: Params, task_file: str, agent: str | None, config_file: str):
    """Verify an impact task using an AI agent."""
    cfg_path = Path(config_file)
    if not cfg_path.exists():
        u.pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)

    config = Config(obj, cfg_path)

    # Parse task file
    task_path = Path(task_file).resolve()
    lg.info(f'Verifying task: {task_path}')

    task_info: ImpactTaskInfo = parse_impact_task(task_path)

    # Validate: must be an impact task
    if not task_info.task_id.startswith('TASK-IMPACT-'):
        u.pprint(f'[red]Error: Unsupported task type. Only TASK-IMPACT-* tasks are supported (got "{task_info.task_id}").[/red]')
        sys.exit(1)

    # Validate: must be open
    if task_info.status != 'open':
        u.pprint(f'[yellow]Task is not open (status: {task_info.status}). Nothing to verify.[/yellow]')
        sys.exit(0)

    # Warn if repo is dirty
    _warn_if_dirty(config)

    # Resolve repo paths for parent and child
    parent_repo_path = _resolve_repo_path(config, task_info.parent_file_path)
    child_repo_path = _resolve_repo_path(config, task_info.child_file_path)

    # Resolve agent
    agent_name = agent or config.ai.agent
    registry = load_agent_registry(config)
    agent_config = resolve_agent(registry, agent_name)
    lg.info(f'Using agent: {agent_name} ({agent_config.get("description", "")})')

    # Render prompt
    prompt = render_verify_prompt(
        config=config,
        task_file_path=str(task_path),
        parent_aid=task_info.parent_aid,
        parent_atype=task_info.parent_atype,
        parent_file_path=str(config.base_dir() / task_info.parent_file_path),
        parent_repo_path=parent_repo_path,
        parent_revision=task_info.parent_revision,
        child_aid=task_info.child_aid,
        child_atype=task_info.child_atype,
        child_file_path=str(config.base_dir() / task_info.child_file_path),
        child_repo_path=child_repo_path,
    )

    # Invoke agent
    u.pprint(f'[blue]Invoking agent "{agent_name}" to verify task {task_info.task_id}...[/blue]')
    exit_code = invoke_agent(agent_config, prompt, working_dir=config.base_dir())

    if exit_code != 0:
        u.pprint(f'[red]Agent exited with code {exit_code}. Aborting verification.[/red]')
        sys.exit(1)

    # Post-edit validation
    is_valid, message = validate_task_post_edit(task_path, task_info.task_id)

    if not is_valid:
        u.pprint(f'[red]Agent produced invalid output: {message}[/red]')
        u.pprint('[yellow]Task file may be corrupted. Use `git checkout` to recover if needed.[/yellow]')
        sys.exit(1)

    # Report result
    # Re-read to check final status
    from syntagmax.ai import _parse_frontmatter

    final_content = task_path.read_text(encoding='utf-8')
    final_fm = _parse_frontmatter(final_content)
    final_status = final_fm.get('status', 'unknown') if final_fm else 'unknown'

    if final_status == 'closed':
        u.pprint(f'[green]✓ Task {task_info.task_id} verified and closed.[/green]')
    else:
        u.pprint(f'[yellow]Task {task_info.task_id} requires more work (status: {final_status}).[/yellow]')


def _warn_if_dirty(config: Config) -> None:
    """Emit a warning if the repository is dirty."""
    try:
        repo = git.Repo(config.base_dir(), search_parent_directories=True)
        if repo.is_dirty() or repo.untracked_files:
            lg.warning('Repository has uncommitted changes. Proceeding anyway.')
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        pass


def _resolve_repo_path(config: Config, file_path: str) -> str:
    """Resolve the repository root for an artifact file path."""
    abs_path = (config.base_dir() / file_path).resolve()
    try:
        repo = git.Repo(abs_path.parent, search_parent_directories=True)
        return str(Path(repo.working_tree_dir).resolve())
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        lg.warning(f'Could not resolve repository for {file_path}, using base_dir')
        return str(config.base_dir().resolve())
