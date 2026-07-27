# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta
from pathlib import Path


from syntagmax.artifact import Artifact, Revision, ParentLink, LineLocation
from syntagmax.config import Config, InputRecord, Params
from syntagmax.tasks import (
    IMPLICIT_TASK_METAMODEL,
    TaskData,
    generate_task_id,
    sanitize_filename,
    render_task_file,
    scan_existing_tasks,
    should_generate_task,
    generate_tasks,
    _build_template_env,
    _parse_frontmatter,
)


class MockRevision(Revision):
    def __init__(self, hash_short, timestamp):
        super().__init__(
            hash_long=hash_short * 6,
            hash_short=hash_short,
            timestamp=timestamp,
            author_email='test@example.com',
        )


def _make_config(tmp_path, extra_toml=''):
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

[metamodel]
filename = "project.syntagmax"

{extra_toml}
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

    # Create directories
    (tmp_path / 'REQ').mkdir(exist_ok=True)
    (tmp_path / 'SYS').mkdir(exist_ok=True)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    return Config(params, config_path)


# --- Task ID generation ---


def test_generate_task_id():
    assert generate_task_id('REQ-001', 'SYS-001') == 'TASK-IMPACT-REQ-001-SYS-001'


def test_generate_task_id_special_chars():
    assert generate_task_id('REQ/001', 'SYS:002') == 'TASK-IMPACT-REQ/001-SYS:002'


# --- Filename sanitization ---


def test_sanitize_filename_clean():
    assert sanitize_filename('TASK-IMPACT-REQ-001-SYS-001.md') == 'TASK-IMPACT-REQ-001-SYS-001.md'


def test_sanitize_filename_unsafe_chars():
    assert sanitize_filename('TASK-IMPACT-REQ/001-SYS:002.md') == 'TASK-IMPACT-REQ-001-SYS-002.md'


def test_sanitize_filename_all_unsafe():
    result = sanitize_filename('a/b\\c:d*e?f"g<h>i|j.md')
    assert '/' not in result
    assert '\\' not in result
    assert ':' not in result
    assert '*' not in result
    assert '?' not in result
    assert '"' not in result
    assert '<' not in result
    assert '>' not in result
    assert '|' not in result


# --- De-duplication logic ---


def test_should_generate_task_missing():
    assert should_generate_task('TASK-1', 'abc', 'def', {}) is True


def test_should_generate_task_revisions_match():
    existing = {'TASK-1': {'status': 'open', 'parent_revision': 'abc', 'child_revision': 'def'}}
    assert should_generate_task('TASK-1', 'abc', 'def', existing) is False


def test_should_generate_task_revisions_match_closed():
    """Even if closed, revisions match means skip."""
    existing = {'TASK-1': {'status': 'closed', 'parent_revision': 'abc', 'child_revision': 'def'}}
    assert should_generate_task('TASK-1', 'abc', 'def', existing) is False


def test_should_generate_task_parent_revision_differs():
    existing = {'TASK-1': {'status': 'open', 'parent_revision': 'abc', 'child_revision': 'def'}}
    assert should_generate_task('TASK-1', 'xyz', 'def', existing) is True


def test_should_generate_task_child_revision_differs():
    existing = {'TASK-1': {'status': 'open', 'parent_revision': 'abc', 'child_revision': 'def'}}
    assert should_generate_task('TASK-1', 'abc', 'xyz', existing) is True


# --- Frontmatter parsing ---


def test_parse_frontmatter_valid():
    content = '---\nid: TASK-1\nstatus: open\nparent_revision: "abc"\n---\n# Body\n'
    result = _parse_frontmatter(content)
    assert result == {'id': 'TASK-1', 'status': 'open', 'parent_revision': 'abc'}


def test_parse_frontmatter_no_frontmatter():
    content = '# Just a heading\nSome body text.'
    assert _parse_frontmatter(content) is None


def test_parse_frontmatter_malformed():
    content = '---\ninvalid: [yaml: broken\n---\n'
    assert _parse_frontmatter(content) is None


def test_parse_frontmatter_no_closing():
    content = '---\nid: TASK-1\nstatus: open\n'
    assert _parse_frontmatter(content) is None


# --- Scan existing tasks ---


def test_scan_existing_tasks_empty_dir(tmp_path):
    assert scan_existing_tasks(tmp_path) == {}


def test_scan_existing_tasks_nonexistent_dir(tmp_path):
    assert scan_existing_tasks(tmp_path / 'nonexistent') == {}


def test_scan_existing_tasks_with_files(tmp_path):
    (tmp_path / 'TASK-1.md').write_text(
        '---\nid: TASK-1\nstatus: open\nparent_revision: "abc"\nchild_revision: "def"\n---\n# Body\n',
        encoding='utf-8',
    )
    (tmp_path / 'TASK-2.md').write_text(
        '---\nid: TASK-2\nstatus: closed\nparent_revision: "xyz"\nchild_revision: "uvw"\n---\n# Body\n',
        encoding='utf-8',
    )
    result = scan_existing_tasks(tmp_path)
    assert result == {
        'TASK-1': {'status': 'open', 'parent_revision': 'abc', 'child_revision': 'def'},
        'TASK-2': {'status': 'closed', 'parent_revision': 'xyz', 'child_revision': 'uvw'},
    }


def test_scan_existing_tasks_malformed_skipped(tmp_path):
    (tmp_path / 'good.md').write_text('---\nid: TASK-1\nstatus: open\n---\n', encoding='utf-8')
    (tmp_path / 'bad.md').write_text('not frontmatter at all', encoding='utf-8')
    result = scan_existing_tasks(tmp_path)
    assert 'TASK-1' in result
    assert len(result) == 1


def test_scan_existing_tasks_missing_status(tmp_path):
    (tmp_path / 'task.md').write_text('---\nid: TASK-1\nparent_revision: "x"\n---\n', encoding='utf-8')
    result = scan_existing_tasks(tmp_path)
    assert result['TASK-1']['status'] == 'open'


# --- Implicit metamodel injection ---


def test_inject_task_metamodel_adds_task(tmp_path):
    config = _make_config(tmp_path)
    assert 'TASK' in config.metamodel['artifacts']
    assert config.metamodel['artifacts']['TASK'] == IMPLICIT_TASK_METAMODEL


def test_inject_task_metamodel_preserves_existing(tmp_path):
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"

[impact]
enabled = true
tasks_enabled = true

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )

    metamodel_path = tmp_path / '.syntagmax' / 'project.syntagmax'
    metamodel_path.write_text(
        """artifact REQ:
    id is string
    attribute contents is mandatory string

artifact TASK:
    id is string
    attribute contents is mandatory string
    attribute status is mandatory enum [open, closed, in_progress]
""",
        encoding='utf-8',
    )
    (tmp_path / 'REQ').mkdir(exist_ok=True)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_path)

    # Should NOT overwrite user-defined TASK
    task_attrs = config.metamodel['artifacts']['TASK']['attributes']
    status_rules = task_attrs['status']
    # User defined has 3 values (open, closed, in_progress)
    assert 'in_progress' in status_rules[0]['type_info']['allowed']


def test_inject_task_metamodel_disabled(tmp_path):
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"

[impact]
enabled = true
tasks_enabled = false

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )

    metamodel_path = tmp_path / '.syntagmax' / 'project.syntagmax'
    metamodel_path.write_text(
        """artifact REQ:
    id is string
    attribute contents is mandatory string
""",
        encoding='utf-8',
    )
    (tmp_path / 'REQ').mkdir(exist_ok=True)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_path)

    # TASK should NOT be injected
    assert 'TASK' not in config.metamodel['artifacts']


def test_inject_task_metamodel_custom_atype_map(tmp_path):
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"

[impact]
enabled = true
tasks_enabled = true

[impact.task_atype_map]
"SYS/REQ" = "REVIEW"

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )

    metamodel_path = tmp_path / '.syntagmax' / 'project.syntagmax'
    metamodel_path.write_text(
        """artifact REQ:
    id is string
    attribute contents is mandatory string
""",
        encoding='utf-8',
    )
    (tmp_path / 'REQ').mkdir(exist_ok=True)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_path)

    # Both TASK (default) and REVIEW (from map) should be injected
    assert 'TASK' in config.metamodel['artifacts']
    assert 'REVIEW' in config.metamodel['artifacts']


# --- Template resolution ---


def test_resolve_task_template_builtin(tmp_path):
    config = _make_config(tmp_path)
    template_dir, template_name = config.resolve_task_template(None)
    assert template_dir is None
    assert template_name == 'task.j2'


def test_resolve_task_template_global(tmp_path):
    config = _make_config(tmp_path, extra_toml='tasks_template = "custom.j2"')
    # Patch impact config after creation since extra_toml goes at wrong level
    # Actually need to set it properly in [impact]
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.write_text(
        """
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"
atype = "REQ"

[impact]
enabled = true
tasks_enabled = true
tasks_template = "custom.j2"

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )
    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_path)

    template_dir, template_name = config.resolve_task_template(None)
    assert template_name == 'custom.j2'
    assert template_dir == config.root_dir()


def test_resolve_task_template_record_override(tmp_path):
    config = _make_config(tmp_path)
    record = InputRecord(
        name='test',
        dir='REQ',
        record_base=tmp_path / 'REQ',
        filepaths=[],
        driver='obsidian',
        default_atype='REQ',
        marker='REQ',
        task_template='templates/my-task.j2',
    )
    template_dir, template_name = config.resolve_task_template(record)
    assert template_name == 'my-task.j2'
    # Should resolve relative to base_dir
    expected_dir = Path(config.base_dir(), 'templates')
    assert template_dir == expected_dir


# --- Template rendering ---


def test_render_task_file(tmp_path):
    config = _make_config(tmp_path)
    env, name = _build_template_env(config, None)

    task_data = TaskData(
        task_id='TASK-IMPACT-REQ-001-SYS-001',
        task_atype='TASK',
        child_aid='REQ-001',
        child_atype='REQ',
        child_record_name='software-requirements',
        child_file_path='REQ/REQ-001.md',
        child_revision_short='c001',
        child_revision_long='c001c001c001',
        parent_aid='SYS-001',
        parent_atype='SYS',
        parent_record_name='system-requirements',
        parent_file_path='SYS/SYS-001.md',
        parent_revision_short='p001',
        parent_revision_long='p001p001p001',
        nominal_revision='old1',
        actual_revision='p001 (2026-07-25 10:00 by test@example.com)',
    )

    content = render_task_file(env, name, task_data)

    # Verify frontmatter
    assert content.startswith('---\n')
    assert 'id: TASK-IMPACT-REQ-001-SYS-001' in content
    assert 'status: open' in content
    assert 'parent_revision: "p001"' in content
    assert 'child_revision: "c001"' in content

    # Verify body
    assert 'REQ-001' in content
    assert 'SYS-001' in content
    assert 'system-requirements' in content
    assert 'software-requirements' in content
    assert 'SYS/SYS-001.md' in content
    assert 'REQ/REQ-001.md' in content
    assert 'p001' in content
    assert 'old1' in content


# --- Full integration: generate_tasks ---


def _make_artifacts_with_suspicious_link(config, parent_rev='p001', child_rev='c001'):
    from benedict import benedict

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


def test_generate_tasks_creates_file(tmp_path):
    config = _make_config(tmp_path)
    artifacts, impact_data = _make_artifacts_with_suspicious_link(config)

    errors = []
    result = generate_tasks(config, artifacts, errors, impact_data)

    assert result['created'] == 1
    assert result['skipped'] == 0

    tasks_dir = config.tasks_dir()
    task_files = list(tasks_dir.glob('*.md'))
    assert len(task_files) == 1
    assert task_files[0].name == 'TASK-IMPACT-REQ-001-SYS-001.md'

    content = task_files[0].read_text(encoding='utf-8')
    assert 'id: TASK-IMPACT-REQ-001-SYS-001' in content
    assert 'status: open' in content
    assert 'parent_revision: "p001"' in content
    assert 'child_revision: "c001"' in content


def test_generate_tasks_skips_matching_revisions(tmp_path):
    config = _make_config(tmp_path)
    artifacts, impact_data = _make_artifacts_with_suspicious_link(config)

    errors = []
    # First run - creates
    result1 = generate_tasks(config, artifacts, errors, impact_data)
    assert result1['created'] == 1

    # Second run - same revisions, should skip
    result2 = generate_tasks(config, artifacts, errors, impact_data)
    assert result2['created'] == 0
    assert result2['skipped'] == 1


def test_generate_tasks_regenerates_on_revision_change(tmp_path):
    config = _make_config(tmp_path)
    artifacts, impact_data = _make_artifacts_with_suspicious_link(config, parent_rev='p001')

    errors = []
    # First run
    result1 = generate_tasks(config, artifacts, errors, impact_data)
    assert result1['created'] == 1

    # Change parent revision
    artifacts2, impact_data2 = _make_artifacts_with_suspicious_link(config, parent_rev='p002')
    result2 = generate_tasks(config, artifacts2, errors, impact_data2)
    assert result2['created'] == 1
    assert result2['skipped'] == 0

    # Verify file updated
    tasks_dir = config.tasks_dir()
    content = (tasks_dir / 'TASK-IMPACT-REQ-001-SYS-001.md').read_text(encoding='utf-8')
    assert 'parent_revision: "p002"' in content


def test_generate_tasks_disabled(tmp_path):
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"

[impact]
enabled = true
tasks_enabled = false

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )
    metamodel_path = tmp_path / '.syntagmax' / 'project.syntagmax'
    metamodel_path.write_text('artifact REQ:\n    id is string\n    attribute contents is mandatory string\n', encoding='utf-8')
    (tmp_path / 'REQ').mkdir(exist_ok=True)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_path)

    from benedict import benedict

    impact_data = benedict()
    impact_data['suspicious_links'] = [{
        'artifact_aid': 'REQ-001', 'artifact_atype': 'REQ',
        'parent_aid': 'SYS-001', 'parent_atype': 'SYS',
        'nominal_revision': 'old', 'actual_revision': 'new',
    }]

    result = generate_tasks(config, {}, [], impact_data)
    assert result == {'created': 0, 'skipped': 0}
    assert not config.tasks_dir().exists()


def test_generate_tasks_atype_map(tmp_path):
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
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

[impact.task_atype_map]
"SYS/REQ" = "REVIEW"

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

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_path)

    artifacts, impact_data = _make_artifacts_with_suspicious_link(config)
    errors = []
    result = generate_tasks(config, artifacts, errors, impact_data)

    assert result['created'] == 1
    # The task file content should reference the REVIEW atype indirectly
    # (the template doesn't render atype in frontmatter, but the function used it)


def test_generate_tasks_sanitizes_filenames(tmp_path):
    config = _make_config(tmp_path)

    from benedict import benedict

    now = datetime.now()

    parent = Artifact(config)
    parent.aid = 'SYS/001'
    parent.atype = 'SYS'
    parent.revisions = {MockRevision('p001', now)}
    parent.location = LineLocation('SYS/SYS-001.md', (1, 10))
    parent.record = InputRecord(
        name='sys', dir='SYS', record_base=Path('.'), filepaths=[], driver='obsidian', default_atype='SYS', marker='SYS'
    )

    child = Artifact(config)
    child.aid = 'REQ:001'
    child.atype = 'REQ'
    child.revisions = {MockRevision('c001', now - timedelta(hours=1))}
    child.parent_links = [ParentLink(pid='SYS/001', nominal_revision='old1', is_suspicious=True)]
    child.location = LineLocation('REQ/REQ-001.md', (1, 10))
    child.record = InputRecord(
        name='reqs', dir='REQ', record_base=Path('.'), filepaths=[], driver='obsidian', default_atype='REQ', marker='REQ'
    )

    artifacts = {'SYS/001': parent, 'REQ:001': child}
    impact_data = benedict()
    impact_data['suspicious_links'] = [
        {
            'artifact_aid': 'REQ:001',
            'artifact_atype': 'REQ',
            'parent_aid': 'SYS/001',
            'parent_atype': 'SYS',
            'nominal_revision': 'old1',
            'actual_revision': 'p001',
        }
    ]

    errors = []
    result = generate_tasks(config, artifacts, errors, impact_data)
    assert result['created'] == 1

    tasks_dir = config.tasks_dir()
    task_files = list(tasks_dir.glob('*.md'))
    assert len(task_files) == 1
    # Filename should have unsafe chars replaced
    assert '/' not in task_files[0].name
    assert ':' not in task_files[0].name
    assert task_files[0].name == 'TASK-IMPACT-REQ-001-SYS-001.md'



# --- CLI --tasks override tests ---


def test_tasks_cli_override_enables_tasks(tmp_path):
    """When --tasks flag is passed, tasks_enabled should be True even if config says false."""
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"

[impact]
enabled = true
tasks_enabled = false

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )

    metamodel_path = tmp_path / '.syntagmax' / 'project.syntagmax'
    metamodel_path.write_text(
        """artifact REQ:
    id is string
    attribute contents is mandatory string
""",
        encoding='utf-8',
    )
    (tmp_path / 'REQ').mkdir(exist_ok=True)

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, tasks=True, output='console')
    config = Config(params, config_path)

    # tasks_enabled should be overridden to True
    assert config.impact.tasks_enabled is True
    # TASK metamodel should be injected
    assert 'TASK' in config.metamodel['artifacts']


def test_tasks_cli_override_not_set_uses_config(tmp_path):
    """When --tasks flag is NOT passed, config value is respected."""
    config_path = tmp_path / '.syntagmax' / 'config.toml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
base = ".."
[[input]]
name = "reqs"
dir = "REQ"
driver = "obsidian"

[impact]
enabled = true
tasks_enabled = false

[metamodel]
filename = "project.syntagmax"
""",
        encoding='utf-8',
    )

    metamodel_path = tmp_path / '.syntagmax' / 'project.syntagmax'
    metamodel_path.write_text(
        """artifact REQ:
    id is string
    attribute contents is mandatory string
""",
        encoding='utf-8',
    )
    (tmp_path / 'REQ').mkdir(exist_ok=True)

    # No 'tasks' key in params - simulates CLI without --tasks
    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True, output='console')
    config = Config(params, config_path)

    # tasks_enabled should remain False from config
    assert config.impact.tasks_enabled is False
    # TASK metamodel should NOT be injected
    assert 'TASK' not in config.metamodel['artifacts']


def test_tasks_cli_flag_accepted():
    """The --tasks flag should be accepted by the analyze command without parse errors."""
    from click.testing import CliRunner
    from syntagmax.cli import rms

    runner = CliRunner()
    # Invoke with --tasks on a nonexistent config; we only care about CLI parsing, not execution
    result = runner.invoke(rms, ['analyze', '--tasks'])
    # Should NOT fail with "No such option: --tasks" (exit_code 2 = usage error)
    assert result.exit_code != 2, f"CLI rejected --tasks flag: {result.output}"
