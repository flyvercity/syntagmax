# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: Tests for the redirectable impact task output directory (impact.task_dir).

from datetime import datetime, timedelta
from pathlib import Path

from benedict import benedict

from syntagmax.artifact import Artifact, Revision, ParentLink, LineLocation
from syntagmax.config import Config, InputRecord, Params
from syntagmax.tasks import generate_tasks


class MockRevision(Revision):
    def __init__(self, hash_short, timestamp):
        super().__init__(
            hash_long=hash_short * 6,
            hash_short=hash_short,
            timestamp=timestamp,
            author_email='test@example.com',
        )


def _make_config(tmp_path, extra_impact_toml=''):
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        f"""
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"
atype = "REQ"

[[input]]
name = "sys"
dir = "SYS"
driver = "obsidian"
atype = "SYS"

[impact]
enabled = true
tasks_enabled = true
{extra_impact_toml}

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )

    metamodel_path = tmp_path / '.syntagmax' / 'project.syntagmax'
    metamodel_path.write_text(
        """artifact SYS:
    id is string
    attribute contents is mandatory string

artifact REQ:
    id is string
    attribute contents is mandatory string
    attribute parent is optional reference to parent

trace from REQ to SYS is mandatory via commit
""",
        encoding='utf-8',
    )

    (tmp_path / 'REQ').mkdir(exist_ok=True)
    (tmp_path / 'SYS').mkdir(exist_ok=True)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True)
    return Config(params, config_path)


def _make_artifacts_with_suspicious_link(config, parent_rev='p001', child_rev='c001'):
    now = datetime.now()

    parent = Artifact(config)
    parent.aid = 'SYS-001'
    parent.atype = 'SYS'
    parent.revisions = {MockRevision(parent_rev, now)}
    parent.location = LineLocation('SYS/SYS-001.md', (1, 10))
    parent.record = InputRecord(
        name='system-requirements',
        dir='SYS',
        record_base=Path('.'),
        filepaths=[],
        driver='obsidian',
        default_atype='SYS',
        marker='SYS',
    )

    child = Artifact(config)
    child.aid = 'REQ-001'
    child.atype = 'REQ'
    child.revisions = {MockRevision(child_rev, now - timedelta(hours=1))}
    child.parent_links = [ParentLink(pid='SYS-001', nominal_revision='old1', is_suspicious=True)]
    child.location = LineLocation('REQ/REQ-001.md', (1, 10))
    child.record = InputRecord(
        name='software-requirements',
        dir='REQ',
        record_base=Path('.'),
        filepaths=[],
        driver='obsidian',
        default_atype='REQ',
        marker='REQ',
    )

    artifacts = {'SYS-001': parent, 'REQ-001': child}

    impact_data = benedict()
    impact_data['suspicious_links'] = [
        {
            'artifact_aid': 'REQ-001',
            'artifact_atype': 'REQ',
            'parent_aid': 'SYS-001',
            'parent_atype': 'SYS',
            'nominal_revision': 'old1',
            'actual_revision': f'{parent_rev} (2026-07-25 10:00 by test@example.com)',
        }
    ]
    impact_data['total_suspicious'] = 1

    return artifacts, impact_data


# --- Config.task_dir() resolver ---


def test_task_dir_unset_matches_tasks_dir(tmp_path):
    """When task_dir is unset, Config.task_dir() is byte-identical to tasks_dir()."""
    config = _make_config(tmp_path)
    assert config.impact.task_dir is None
    assert config.task_dir() == config.tasks_dir()
    assert config.task_dir() == Path(config.root_dir(), 'tasks/')


def test_task_dir_relative_resolved_against_root(tmp_path):
    """A relative task_dir resolves under root_dir."""
    config = _make_config(tmp_path, extra_impact_toml='task_dir = "out/tasks"')
    assert config.task_dir() == Path(config.root_dir(), 'out/tasks')


def test_task_dir_absolute_honoured_as_is(tmp_path):
    """An absolute task_dir is honoured verbatim."""
    abs_dir = (tmp_path / 'external' / 'tasks').resolve()
    config = _make_config(tmp_path, extra_impact_toml=f'task_dir = {abs_dir.as_posix()!r}')
    assert config.task_dir() == Path(abs_dir)
    assert config.task_dir().is_absolute()


# --- generate_tasks write routing ---


def test_generate_tasks_unset_writes_default_location(tmp_path):
    """Unset task_dir → tasks written under <root>/tasks/ (unchanged behaviour)."""
    config = _make_config(tmp_path)
    artifacts, impact_data = _make_artifacts_with_suspicious_link(config)

    result = generate_tasks(config, artifacts, [], impact_data)
    assert result['created'] == 1

    default_dir = Path(config.root_dir(), 'tasks/')
    task_files = list(default_dir.glob('*.md'))
    assert len(task_files) == 1
    assert task_files[0].name == 'TASK-IMPACT-REQ-001-SYS-001.md'


def test_generate_tasks_relative_task_dir(tmp_path):
    """Relative task_dir = "out/tasks" → written under <root>/out/tasks."""
    config = _make_config(tmp_path, extra_impact_toml='task_dir = "out/tasks"')
    artifacts, impact_data = _make_artifacts_with_suspicious_link(config)

    result = generate_tasks(config, artifacts, [], impact_data)
    assert result['created'] == 1

    redirected = Path(config.root_dir(), 'out/tasks')
    task_files = list(redirected.glob('*.md'))
    assert len(task_files) == 1
    assert task_files[0].name == 'TASK-IMPACT-REQ-001-SYS-001.md'

    # Default location must NOT have been used
    default_dir = Path(config.root_dir(), 'tasks/')
    assert not default_dir.exists() or not list(default_dir.glob('*.md'))


def test_generate_tasks_absolute_task_dir_outside_root(tmp_path):
    """Absolute task_dir → written at that absolute path, outside the root."""
    outside = (tmp_path.parent / 'outside_tasks').resolve()
    config = _make_config(tmp_path, extra_impact_toml=f'task_dir = {outside.as_posix()!r}')
    artifacts, impact_data = _make_artifacts_with_suspicious_link(config)

    result = generate_tasks(config, artifacts, [], impact_data)
    assert result['created'] == 1

    task_files = list(Path(outside).glob('*.md'))
    assert len(task_files) == 1
    assert task_files[0].name == 'TASK-IMPACT-REQ-001-SYS-001.md'

    # Confirm it is outside the project root
    assert config.root_dir() not in Path(outside).parents

    # Default location must NOT have been used
    default_dir = Path(config.root_dir(), 'tasks/')
    assert not default_dir.exists() or not list(default_dir.glob('*.md'))
