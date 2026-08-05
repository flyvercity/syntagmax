# SPDX-License-Identifier: MIT
# Tests for syntagmax.ai module.

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from syntagmax.ai import (
    ArtifactPaths,
    _parse_frontmatter,
    invoke_agent,
    load_agent_registry,
    parse_impact_task,
    render_verify_prompt,
    resolve_agent,
    resolve_artifact_paths,
    validate_child_post_edit,
    validate_task_post_edit,
)
from syntagmax.errors import FatalError


# --- _parse_frontmatter ---


def test_parse_frontmatter_valid():
    content = "---\nid: TASK-001\nstatus: open\n---\n# Body"
    result = _parse_frontmatter(content)
    assert result == {'id': 'TASK-001', 'status': 'open'}


def test_parse_frontmatter_no_frontmatter():
    content = "# Just a heading\nSome body text."
    assert _parse_frontmatter(content) is None


def test_parse_frontmatter_malformed_yaml():
    content = "---\n: : invalid: [yaml\n---\nBody"
    assert _parse_frontmatter(content) is None


def test_parse_frontmatter_non_dict():
    content = "---\n- item1\n- item2\n---\nBody"
    assert _parse_frontmatter(content) is None


def test_parse_frontmatter_empty_frontmatter():
    content = "---\n\n---\nBody"
    assert _parse_frontmatter(content) is None


# --- resolve_agent ---


def test_resolve_agent_found():
    registry = {
        'kiro': {'command': 'kiro-cli {prompt}', 'description': 'Kiro'},
        'claude': {'command': 'claude {prompt}', 'description': 'Claude'},
    }
    result = resolve_agent(registry, 'kiro')
    assert result == {'command': 'kiro-cli {prompt}', 'description': 'Kiro'}


def test_resolve_agent_not_found():
    registry = {
        'kiro': {'command': 'kiro-cli {prompt}', 'description': 'Kiro'},
    }
    with pytest.raises(FatalError, match="Unknown agent 'missing'"):
        resolve_agent(registry, 'missing')


# --- load_agent_registry ---


def test_load_agent_registry_default():
    """Load the built-in agent registry from package resources."""
    config = MagicMock()
    config.ai.agents_file = None

    registry = load_agent_registry(config)
    assert 'kiro' in registry
    assert 'claude' in registry
    assert 'command' in registry['kiro']


def test_load_agent_registry_custom(tmp_path: Path):
    """Load a custom agent registry from a file."""
    agents_yaml = tmp_path / 'custom-agents.yaml'
    agents_yaml.write_text(
        "agents:\n  my-agent:\n    command: 'my-agent {prompt}'\n    description: 'Custom'\n",
        encoding='utf-8',
    )

    config = MagicMock()
    config.ai.agents_file = 'custom-agents.yaml'
    config.root_dir.return_value = tmp_path

    registry = load_agent_registry(config)
    assert 'my-agent' in registry
    assert registry['my-agent']['command'] == 'my-agent {prompt}'


def test_load_agent_registry_custom_missing(tmp_path: Path):
    """Raise FatalError if custom agents file does not exist."""
    config = MagicMock()
    config.ai.agents_file = 'nonexistent.yaml'
    config.root_dir.return_value = tmp_path

    with pytest.raises(FatalError, match='Custom agents file not found'):
        load_agent_registry(config)


def test_load_agent_registry_invalid_format(tmp_path: Path):
    """Raise FatalError if YAML has no 'agents' key."""
    agents_yaml = tmp_path / 'bad.yaml'
    agents_yaml.write_text("something_else:\n  foo: bar\n", encoding='utf-8')

    config = MagicMock()
    config.ai.agents_file = 'bad.yaml'
    config.root_dir.return_value = tmp_path

    with pytest.raises(FatalError, match='missing "agents" key'):
        load_agent_registry(config)


# --- validate_task_post_edit ---


def test_validate_task_post_edit_valid(tmp_path: Path):
    task = tmp_path / 'task.md'
    task.write_text(
        "---\nid: TASK-IMPACT-001\nstatus: closed\n---\n\n## Verification Report\n- **Verdict:** PASS\n",
        encoding='utf-8',
    )
    is_valid, msg = validate_task_post_edit(task, 'TASK-IMPACT-001')
    assert is_valid is True
    assert msg == 'valid'


def test_validate_task_post_edit_id_changed(tmp_path: Path):
    task = tmp_path / 'task.md'
    task.write_text(
        "---\nid: TASK-IMPACT-999\nstatus: closed\n---\n\n## Verification Report\n",
        encoding='utf-8',
    )
    is_valid, msg = validate_task_post_edit(task, 'TASK-IMPACT-001')
    assert is_valid is False
    assert 'ID was modified' in msg


def test_validate_task_post_edit_invalid_status(tmp_path: Path):
    task = tmp_path / 'task.md'
    task.write_text(
        "---\nid: TASK-IMPACT-001\nstatus: pending\n---\n\n## Verification Report\n",
        encoding='utf-8',
    )
    is_valid, msg = validate_task_post_edit(task, 'TASK-IMPACT-001')
    assert is_valid is False
    assert 'Invalid status' in msg


def test_validate_task_post_edit_no_report_section(tmp_path: Path):
    task = tmp_path / 'task.md'
    task.write_text(
        "---\nid: TASK-IMPACT-001\nstatus: open\n---\n\nNo report here.\n",
        encoding='utf-8',
    )
    is_valid, msg = validate_task_post_edit(task, 'TASK-IMPACT-001')
    assert is_valid is False
    assert 'Verification Report' in msg


def test_validate_task_post_edit_no_frontmatter(tmp_path: Path):
    task = tmp_path / 'task.md'
    task.write_text("# Just a heading\n", encoding='utf-8')
    is_valid, msg = validate_task_post_edit(task, 'TASK-IMPACT-001')
    assert is_valid is False
    assert 'no valid frontmatter' in msg


def test_validate_task_post_edit_file_missing(tmp_path: Path):
    task = tmp_path / 'nonexistent.md'
    is_valid, msg = validate_task_post_edit(task, 'TASK-IMPACT-001')
    assert is_valid is False
    assert 'Cannot read' in msg


# --- parse_impact_task ---


VALID_TASK_CONTENT = """\
---
id: TASK-IMPACT-REQ-003-SYS-003
status: open
parent_revision: abc1234
---

## Parent (Updated)
- **ID:** SYS-003
- **Type:** SYS
- **Input Record:** system-requirements
- **File:** system/SYS-003.md

## Child (Outdated)
- **ID:** REQ-003
- **Type:** REQ
- **Input Record:** software-requirements
- **File:** requirements/REQ-003.md
"""


def test_parse_impact_task_valid(tmp_path: Path):
    task = tmp_path / 'task.md'
    task.write_text(VALID_TASK_CONTENT, encoding='utf-8')

    info = parse_impact_task(task)
    assert info.task_id == 'TASK-IMPACT-REQ-003-SYS-003'
    assert info.status == 'open'
    assert info.parent_aid == 'SYS-003'
    assert info.parent_atype == 'SYS'
    assert info.parent_file_path == 'system/SYS-003.md'
    assert info.parent_revision == 'abc1234'
    assert info.child_aid == 'REQ-003'
    assert info.child_atype == 'REQ'
    assert info.child_file_path == 'requirements/REQ-003.md'
    assert info.parent_record_name == 'system-requirements'
    assert info.child_record_name == 'software-requirements'


def test_parse_impact_task_missing_record_names(tmp_path: Path):
    """Legacy task files without Input Record fields default to empty string."""
    content = """\
---
id: TASK-IMPACT-REQ-001-SYS-001
status: open
parent_revision: def5678
---

## Parent (Updated)
- **ID:** SYS-001
- **Type:** SYS
- **File:** system/SYS-001.md

## Child (Outdated)
- **ID:** REQ-001
- **Type:** REQ
- **File:** requirements/REQ-001.md
"""
    task = tmp_path / 'task.md'
    task.write_text(content, encoding='utf-8')

    info = parse_impact_task(task)
    assert info.parent_record_name == ''
    assert info.child_record_name == ''


def test_parse_impact_task_no_frontmatter(tmp_path: Path):
    task = tmp_path / 'task.md'
    task.write_text("# No frontmatter\n", encoding='utf-8')
    with pytest.raises(FatalError, match='no valid frontmatter'):
        parse_impact_task(task)


def test_parse_impact_task_missing_fields(tmp_path: Path):
    content = """\
---
id: TASK-IMPACT-001
status: open
parent_revision: abc1234
---

## Parent (Updated)
- **ID:** SYS-001

## Child (Outdated)
- **ID:** REQ-001
"""
    task = tmp_path / 'task.md'
    task.write_text(content, encoding='utf-8')
    with pytest.raises(FatalError, match='missing required fields'):
        parse_impact_task(task)


# --- resolve_artifact_paths ---


def test_resolve_artifact_paths_via_record(tmp_path: Path):
    """Resolves paths using input record's record_base to find git repo."""
    import git

    # Set up a git repo
    repo = git.Repo.init(str(tmp_path))
    # Create file structure: base_dir = tmp_path/project, record in tmp_path/project/SYS
    project_dir = tmp_path / 'project'
    sys_dir = project_dir / 'SYS'
    sys_dir.mkdir(parents=True)
    sys_file = sys_dir / 'SYS-001.md'
    sys_file.write_text('# SYS-001', encoding='utf-8')
    repo.index.add([str(sys_file.relative_to(tmp_path))])
    repo.index.commit('init')

    # Mock config
    config = MagicMock()
    config.base_dir.return_value = project_dir

    record = MagicMock()
    record.name = 'system-requirements'
    record.record_base = sys_dir
    config.input_records.return_value = [record]

    result = resolve_artifact_paths(config, 'system-requirements', 'SYS/SYS-001.md')

    assert result.repo_root == str(tmp_path.resolve())
    assert result.relative_path == 'project/SYS/SYS-001.md'
    assert '\\' not in result.relative_path  # Forward slashes only
    assert str(sys_file.resolve()) in result.absolute_path


def test_resolve_artifact_paths_fallback_empty_record_name(tmp_path: Path):
    """Falls back to git-walk when record_name is empty."""
    import git

    repo = git.Repo.init(str(tmp_path))
    base_dir = tmp_path / 'base'
    base_dir.mkdir()
    req_file = base_dir / 'REQ-001.md'
    req_file.write_text('# REQ', encoding='utf-8')
    repo.index.add([str(req_file.relative_to(tmp_path))])
    repo.index.commit('init')

    config = MagicMock()
    config.base_dir.return_value = base_dir
    config.input_records.return_value = []

    result = resolve_artifact_paths(config, '', 'REQ-001.md')

    assert result.repo_root == str(tmp_path.resolve())
    assert result.relative_path == 'base/REQ-001.md'
    assert '\\' not in result.relative_path


def test_resolve_artifact_paths_fallback_record_not_found(tmp_path: Path):
    """Falls back to git-walk when record name doesn't match any config record."""
    import git

    repo = git.Repo.init(str(tmp_path))
    base_dir = tmp_path / 'base'
    base_dir.mkdir()
    req_file = base_dir / 'REQ-001.md'
    req_file.write_text('# REQ', encoding='utf-8')
    repo.index.add([str(req_file.relative_to(tmp_path))])
    repo.index.commit('init')

    config = MagicMock()
    config.base_dir.return_value = base_dir

    record = MagicMock()
    record.name = 'other-record'
    config.input_records.return_value = [record]

    result = resolve_artifact_paths(config, 'nonexistent-record', 'REQ-001.md')

    assert result.repo_root == str(tmp_path.resolve())
    assert '\\' not in result.relative_path


def test_resolve_artifact_paths_no_git_repo(tmp_path: Path):
    """Falls back to base_dir when no git repo can be found."""
    base_dir = tmp_path / 'base'
    base_dir.mkdir()
    req_file = base_dir / 'REQ-001.md'
    req_file.write_text('# REQ', encoding='utf-8')

    config = MagicMock()
    config.base_dir.return_value = base_dir
    config.input_records.return_value = []

    result = resolve_artifact_paths(config, '', 'REQ-001.md')

    assert result.repo_root == str(base_dir.resolve())
    assert result.relative_path == 'REQ-001.md'
    assert '\\' not in result.relative_path


# --- invoke_agent ---


@patch('syntagmax.ai.subprocess.run')
@patch('syntagmax.ai.shutil.which', return_value=None)
def test_invoke_agent_success(mock_which, mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=0)
    agent_config = {'command': 'my-agent --exec {prompt}'}

    result = invoke_agent(agent_config, 'test prompt', tmp_path)

    assert result == 0
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    cmd_parts = call_args[0][0]
    assert cmd_parts[0] == 'my-agent'
    assert '--exec' in cmd_parts


@patch('syntagmax.ai.subprocess.run')
@patch('syntagmax.ai.shutil.which', return_value=None)
def test_invoke_agent_nonzero_exit(mock_which, mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=1)
    agent_config = {'command': 'my-agent {prompt}'}

    result = invoke_agent(agent_config, 'prompt', tmp_path)
    assert result == 1


@patch('syntagmax.ai.subprocess.run', side_effect=FileNotFoundError)
@patch('syntagmax.ai.shutil.which', return_value=None)
def test_invoke_agent_executable_not_found(mock_which, mock_run, tmp_path: Path):
    agent_config = {'command': 'nonexistent-agent {prompt}'}
    with pytest.raises(FatalError, match="not found on PATH"):
        invoke_agent(agent_config, 'prompt', tmp_path)


@patch('syntagmax.ai.subprocess.run')
@patch('syntagmax.ai.shutil.which', return_value='/usr/local/bin/my-agent')
def test_invoke_agent_which_resolves(mock_which, mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=0)
    agent_config = {'command': 'my-agent {prompt}'}

    invoke_agent(agent_config, 'prompt', tmp_path)

    call_args = mock_run.call_args
    cmd_parts = call_args[0][0]
    assert cmd_parts[0] == '/usr/local/bin/my-agent'


@patch('syntagmax.ai.subprocess.run')
@patch('syntagmax.ai.shutil.which', return_value=None)
def test_invoke_agent_cleans_temp_file(mock_which, mock_run, tmp_path: Path):
    """Temporary prompt file is deleted after invocation."""
    captured_paths = []

    def capture_run(cmd, **kwargs):
        # The prompt path is the last argument
        for part in cmd:
            if part.endswith('.md'):
                captured_paths.append(part)
        return MagicMock(returncode=0)

    mock_run.side_effect = capture_run
    agent_config = {'command': 'my-agent {prompt}'}

    invoke_agent(agent_config, 'test content', tmp_path)

    assert len(captured_paths) == 1
    # Temp file should be cleaned up
    assert not Path(captured_paths[0]).exists()



# --- render_verify_prompt expanded sections ---


def test_render_verify_prompt_contains_expanded_sections():
    config = MagicMock()
    config.ai.persona = 'You are a systems engineer reviewing requirements traceability.'

    result = render_verify_prompt(
        config=config,
        task_file_path='task.md',
        parent_aid='SYS-001',
        parent_atype='SYS',
        parent_file_path='/repo/SYS-001.md',
        parent_repo_path='/repo',
        parent_relative_path='SYS-001.md',
        parent_revision='abc1234',
        child_aid='REQ-001',
        child_atype='REQ',
        child_file_path='/repo/REQ-001.md',
        child_repo_path='/repo',
        child_relative_path='REQ-001.md',
        agent_name='test-agent',
        amend=False,
    )

    # Assert expanded report sections are present
    assert '### Parent Changes' in result
    assert '### Child Changes' in result
    assert '### Change Mapping' in result
    # Assert relative path fields are present
    assert 'Relative Path (in repo): SYS-001.md' in result
    assert 'Relative Path (in repo): REQ-001.md' in result
    assert '### Rationale' in result

    # Assert metadata fields are present
    assert 'Verdict' in result
    assert 'Agent' in result
    assert 'Date' in result


# --- validate_task_post_edit expanded format ---


def test_validate_task_post_edit_expanded_format(tmp_path: Path):
    task_content = """\
---
id: TASK-IMPACT-REQ-001-SYS-001
status: closed
---

## Verification Report
- **Verdict:** PASS
- **Agent:** test-agent
- **Date:** 2026-08-03
- **Parent revision observed:** abc1234 (dirty: no)
- **Child revision observed:** def5678 (dirty: no)

### Parent Changes
- Added safety requirement clause

### Child Changes
- Updated derived requirement to include safety

### Change Mapping
1. Parent added safety clause → Child updated to include safety requirement

### Rationale
The child correctly derives from the updated parent. PASS.
"""
    task_path = tmp_path / 'task.md'
    task_path.write_text(task_content, encoding='utf-8')

    is_valid, msg = validate_task_post_edit(task_path, 'TASK-IMPACT-REQ-001-SYS-001')
    assert is_valid is True
    assert msg == 'valid'


# --- render_verify_prompt amend modes ---

_RENDER_DEFAULTS = dict(
    task_file_path='task.md',
    parent_aid='SYS-001',
    parent_atype='SYS',
    parent_file_path='/repo/SYS-001.md',
    parent_repo_path='/repo',
    parent_relative_path='SYS-001.md',
    parent_revision='abc1234',
    child_aid='REQ-001',
    child_atype='REQ',
    child_file_path='/repo/REQ-001.md',
    child_repo_path='/repo',
    child_relative_path='REQ-001.md',
    agent_name='test-agent',
)


def _make_config():
    config = MagicMock()
    config.ai.persona = 'You are a systems engineer reviewing requirements traceability.'
    return config


def test_render_verify_prompt_amend_false_contains_recommendation():
    result = render_verify_prompt(config=_make_config(), amend=False, **_RENDER_DEFAULTS)

    assert '### Amendment Recommendation' in result
    assert '### Amendment Applied' not in result
    assert 'Phase 2: Recommendation' in result
    # Child file path must NOT appear in a modify/edit instruction in amend=False mode
    assert 'Do NOT modify the child artifact' in result


def test_render_verify_prompt_amend_true_contains_implementation():
    result = render_verify_prompt(config=_make_config(), amend=True, **_RENDER_DEFAULTS)

    assert '### Amendment Applied' in result
    assert '### Amendment Recommendation' not in result
    assert 'Phase 2: Implementation' in result
    # Child file path appears in the edit instruction
    assert '/repo/REQ-001.md' in result
    # Parent immutability constraint still present
    assert 'Do NOT modify the parent artifact' in result
    # Scope constraint present
    assert 'Do NOT modify any file other than' in result


def test_render_verify_prompt_uncertainty_constraint_amend_false():
    result = render_verify_prompt(config=_make_config(), amend=False, **_RENDER_DEFAULTS)

    assert 'unsure' in result.lower() or 'uncertain' in result.lower()
    assert '### Rationale' in result
    # Must instruct to leave status open and child untouched
    assert 'status: open' in result
    assert 'untouched' in result or 'Do NOT modify the child artifact' in result


def test_render_verify_prompt_uncertainty_constraint_amend_true():
    result = render_verify_prompt(config=_make_config(), amend=True, **_RENDER_DEFAULTS)

    assert 'unsure' in result.lower() or 'uncertain' in result.lower()
    assert '### Rationale' in result
    assert 'status: open' in result


# --- validate_child_post_edit ---


def test_validate_child_post_edit_valid_no_frontmatter(tmp_path: Path):
    child = tmp_path / 'REQ-001.md'
    child.write_text('# REQ-001\nSome content here.\n', encoding='utf-8')
    is_valid, msg = validate_child_post_edit(child)
    assert is_valid is True
    assert msg == 'valid'


def test_validate_child_post_edit_valid_with_frontmatter(tmp_path: Path):
    child = tmp_path / 'REQ-001.md'
    child.write_text(
        '---\nid: REQ-001\nstatus: active\n---\n# REQ-001\nContent.\n',
        encoding='utf-8',
    )
    is_valid, msg = validate_child_post_edit(child)
    assert is_valid is True
    assert msg == 'valid'


def test_validate_child_post_edit_missing_file(tmp_path: Path):
    child = tmp_path / 'nonexistent.md'
    is_valid, msg = validate_child_post_edit(child)
    assert is_valid is False
    assert 'deleted' in msg


def test_validate_child_post_edit_empty_file(tmp_path: Path):
    child = tmp_path / 'REQ-001.md'
    child.write_text('', encoding='utf-8')
    is_valid, msg = validate_child_post_edit(child)
    assert is_valid is False
    assert 'empty' in msg


def test_validate_child_post_edit_broken_frontmatter(tmp_path: Path):
    child = tmp_path / 'REQ-001.md'
    child.write_text('---\n: : invalid: [yaml\n---\nContent.\n', encoding='utf-8')
    is_valid, msg = validate_child_post_edit(child)
    assert is_valid is False
    assert 'frontmatter' in msg
