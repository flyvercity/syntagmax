# SPDX-License-Identifier: MIT
# CLI tests for `syntagmax ai verify --amend`.

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from syntagmax.cli import rms


# Minimal valid task file content for test setup
_TASK_CONTENT_BASE = """\
---
id: TASK-IMPACT-REQ-001-SYS-001
status: open
parent_revision: abc1234
---

## Parent (Updated)
- **ID:** SYS-001
- **Type:** SYS
- **Input Record:** system-requirements
- **File:** system/SYS-001.md

## Child (Outdated)
- **ID:** REQ-001
- **Type:** REQ
- **Input Record:** software-requirements
- **File:** requirements/REQ-001.md
"""

_TASK_CONTENT_CLOSED_NO_AMENDMENT = """\
---
id: TASK-IMPACT-REQ-001-SYS-001
status: closed
parent_revision: abc1234
---

## Parent (Updated)
- **ID:** SYS-001
- **Type:** SYS
- **Input Record:** system-requirements
- **File:** system/SYS-001.md

## Child (Outdated)
- **ID:** REQ-001
- **Type:** REQ
- **Input Record:** software-requirements
- **File:** requirements/REQ-001.md

## Verification Report
- **Verdict:** PASS
- **Agent:** test-agent
- **Date:** 2026-08-05
- **Parent revision observed:** abc1234 (dirty: no)
- **Child revision observed:** def5678 (dirty: no)

### Parent Changes
No meaningful changes observed.

### Child Changes
No changes observed.

### Change Mapping
1. No parent changes requiring child updates.

### Rationale
Child remains consistent with parent. PASS.
"""

_TASK_CONTENT_CLOSED_WITH_AMENDMENT = """\
---
id: TASK-IMPACT-REQ-001-SYS-001
status: closed
parent_revision: abc1234
---

## Parent (Updated)
- **ID:** SYS-001
- **Type:** SYS
- **Input Record:** system-requirements
- **File:** system/SYS-001.md

## Child (Outdated)
- **ID:** REQ-001
- **Type:** REQ
- **Input Record:** software-requirements
- **File:** requirements/REQ-001.md

## Verification Report
- **Verdict:** FAIL
- **Agent:** test-agent
- **Date:** 2026-08-05
- **Parent revision observed:** abc1234 (dirty: no)
- **Child revision observed:** def5678 (dirty: no)

### Parent Changes
- Added safety requirement clause.

### Child Changes
- Updated to include safety requirement.

### Change Mapping
1. Parent added safety clause → Child updated to include safety requirement.

### Rationale
Child updated to reflect parent change. PASS after amendment.

### Amendment Applied
- Added safety requirement clause to REQ-001 per parent SYS-001 change.
"""


def _make_runner_invoke(task_path: Path, extra_args: list[str], config_path: Path):
    """Helper: invoke rms ai verify via CliRunner."""
    runner = CliRunner()
    args = [
        '-f', str(config_path),
        'ai', 'verify', str(task_path),
    ] + extra_args
    return runner.invoke(rms, args, catch_exceptions=False)


@patch('syntagmax.cli_ai.invoke_agent', return_value=0)
@patch('syntagmax.cli_ai.resolve_artifact_paths')
@patch('syntagmax.cli_ai.load_agent_registry')
@patch('syntagmax.cli_ai.Config')
def test_cli_verify_amend_pass_no_amendment(
    mock_config_cls, mock_registry, mock_resolve_paths, mock_invoke, tmp_path: Path
):
    """--amend set but agent closes task without Amendment Applied → 'verified and closed'."""
    # Set up config file
    config_file = tmp_path / '.syntagmax' / 'config.toml'
    config_file.parent.mkdir(parents=True)
    config_file.write_text('[ai]\nagent = "test-agent"\n', encoding='utf-8')

    # Set up task file (starts open)
    task_file = tmp_path / 'task.md'
    task_file.write_text(_TASK_CONTENT_BASE, encoding='utf-8')

    # After agent runs, write closed content WITHOUT ### Amendment Applied
    def fake_invoke(agent_config, prompt, working_dir):
        task_file.write_text(_TASK_CONTENT_CLOSED_NO_AMENDMENT, encoding='utf-8')
        return 0

    mock_invoke.side_effect = fake_invoke

    # Child artifact to validate
    child_file = tmp_path / 'REQ-001.md'
    child_file.write_text('# REQ-001\nContent.\n', encoding='utf-8')

    # Mock config
    cfg = MagicMock()
    cfg.ai.agent = 'test-agent'
    cfg.ai.persona = 'You are an engineer.'
    cfg.base_dir.return_value = tmp_path
    cfg.root_dir.return_value = tmp_path
    mock_config_cls.return_value = cfg

    # Mock registry
    mock_registry.return_value = {'test-agent': {'command': 'test-agent {prompt}', 'description': 'Test'}}

    # Mock path resolution
    paths = MagicMock()
    paths.repo_root = str(tmp_path)
    paths.relative_path = 'REQ-001.md'
    paths.absolute_path = str(child_file)
    mock_resolve_paths.return_value = paths

    with patch('syntagmax.cli_ai.validate_child_post_edit') as mock_child_val:
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['-f', str(config_file), 'ai', 'verify', str(task_file), '--amend'],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert 'verified and closed' in result.output
    assert 'amended' not in result.output
    # Child validation should NOT be called when no Amendment Applied present
    mock_child_val.assert_not_called()


@patch('syntagmax.cli_ai.invoke_agent', return_value=0)
@patch('syntagmax.cli_ai.resolve_artifact_paths')
@patch('syntagmax.cli_ai.load_agent_registry')
@patch('syntagmax.cli_ai.Config')
def test_cli_verify_amend_pass_with_amendment(
    mock_config_cls, mock_registry, mock_resolve_paths, mock_invoke, tmp_path: Path
):
    """--amend set and agent applies amendment → 'verified and child artifact amended' + git diff hint."""
    config_file = tmp_path / '.syntagmax' / 'config.toml'
    config_file.parent.mkdir(parents=True)
    config_file.write_text('[ai]\nagent = "test-agent"\n', encoding='utf-8')

    task_file = tmp_path / 'task.md'
    task_file.write_text(_TASK_CONTENT_BASE, encoding='utf-8')

    def fake_invoke(agent_config, prompt, working_dir):
        task_file.write_text(_TASK_CONTENT_CLOSED_WITH_AMENDMENT, encoding='utf-8')
        return 0

    mock_invoke.side_effect = fake_invoke

    child_file = tmp_path / 'REQ-001.md'
    child_file.write_text('# REQ-001\nUpdated content.\n', encoding='utf-8')

    cfg = MagicMock()
    cfg.ai.agent = 'test-agent'
    cfg.ai.persona = 'You are an engineer.'
    cfg.base_dir.return_value = tmp_path
    cfg.root_dir.return_value = tmp_path
    mock_config_cls.return_value = cfg

    mock_registry.return_value = {'test-agent': {'command': 'test-agent {prompt}', 'description': 'Test'}}

    paths = MagicMock()
    paths.repo_root = str(tmp_path)
    paths.relative_path = 'REQ-001.md'
    paths.absolute_path = str(child_file)
    mock_resolve_paths.return_value = paths

    with patch('syntagmax.cli_ai.validate_child_post_edit', return_value=(True, 'valid')) as mock_child_val:
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['-f', str(config_file), 'ai', 'verify', str(task_file), '--amend'],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert 'verified and child artifact amended' in result.output
    assert 'git diff' in result.output
    mock_child_val.assert_called_once()


@patch('syntagmax.cli_ai.invoke_agent', return_value=0)
@patch('syntagmax.cli_ai.resolve_artifact_paths')
@patch('syntagmax.cli_ai.load_agent_registry')
@patch('syntagmax.cli_ai.Config')
def test_cli_verify_amend_child_validation_failure(
    mock_config_cls, mock_registry, mock_resolve_paths, mock_invoke, tmp_path: Path
):
    """Child validation fails after --amend → exit 1 with integrity check message."""
    config_file = tmp_path / '.syntagmax' / 'config.toml'
    config_file.parent.mkdir(parents=True)
    config_file.write_text('[ai]\nagent = "test-agent"\n', encoding='utf-8')

    task_file = tmp_path / 'task.md'
    task_file.write_text(_TASK_CONTENT_BASE, encoding='utf-8')

    def fake_invoke(agent_config, prompt, working_dir):
        task_file.write_text(_TASK_CONTENT_CLOSED_WITH_AMENDMENT, encoding='utf-8')
        return 0

    mock_invoke.side_effect = fake_invoke

    child_file = tmp_path / 'REQ-001.md'
    child_file.write_text('# REQ-001\nContent.\n', encoding='utf-8')

    cfg = MagicMock()
    cfg.ai.agent = 'test-agent'
    cfg.ai.persona = 'You are an engineer.'
    cfg.base_dir.return_value = tmp_path
    cfg.root_dir.return_value = tmp_path
    mock_config_cls.return_value = cfg

    mock_registry.return_value = {'test-agent': {'command': 'test-agent {prompt}', 'description': 'Test'}}

    paths = MagicMock()
    paths.repo_root = str(tmp_path)
    paths.relative_path = 'REQ-001.md'
    paths.absolute_path = str(child_file)
    mock_resolve_paths.return_value = paths

    with patch(
        'syntagmax.cli_ai.validate_child_post_edit',
        return_value=(False, 'Child artifact is empty after amendment'),
    ):
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['-f', str(config_file), 'ai', 'verify', str(task_file), '--amend'],
        )

    assert result.exit_code == 1
    assert 'Child artifact integrity check failed' in result.output


@patch('syntagmax.cli_ai.invoke_agent', return_value=0)
@patch('syntagmax.cli_ai.resolve_artifact_paths')
@patch('syntagmax.cli_ai.load_agent_registry')
@patch('syntagmax.cli_ai.Config')
def test_cli_verify_no_amend_flag(
    mock_config_cls, mock_registry, mock_resolve_paths, mock_invoke, tmp_path: Path
):
    """No --amend flag → child validation never called, 'verified and closed' message."""
    config_file = tmp_path / '.syntagmax' / 'config.toml'
    config_file.parent.mkdir(parents=True)
    config_file.write_text('[ai]\nagent = "test-agent"\n', encoding='utf-8')

    task_file = tmp_path / 'task.md'
    task_file.write_text(_TASK_CONTENT_BASE, encoding='utf-8')

    def fake_invoke(agent_config, prompt, working_dir):
        task_file.write_text(_TASK_CONTENT_CLOSED_NO_AMENDMENT, encoding='utf-8')
        return 0

    mock_invoke.side_effect = fake_invoke

    child_file = tmp_path / 'REQ-001.md'
    child_file.write_text('# REQ-001\nContent.\n', encoding='utf-8')

    cfg = MagicMock()
    cfg.ai.agent = 'test-agent'
    cfg.ai.persona = 'You are an engineer.'
    cfg.base_dir.return_value = tmp_path
    cfg.root_dir.return_value = tmp_path
    mock_config_cls.return_value = cfg

    mock_registry.return_value = {'test-agent': {'command': 'test-agent {prompt}', 'description': 'Test'}}

    paths = MagicMock()
    paths.repo_root = str(tmp_path)
    paths.relative_path = 'REQ-001.md'
    paths.absolute_path = str(child_file)
    mock_resolve_paths.return_value = paths

    with patch('syntagmax.cli_ai.validate_child_post_edit') as mock_child_val:
        runner = CliRunner()
        result = runner.invoke(
            rms,
            ['-f', str(config_file), 'ai', 'verify', str(task_file)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert 'verified and closed' in result.output
    assert 'amended' not in result.output
    mock_child_val.assert_not_called()
