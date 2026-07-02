import textwrap

from syntagmax.config import Config, Params
from syntagmax.edit import renumber_artifacts
from syntagmax.extract import extract


def test_multiple_records_same_driver(tmp_path):
    project_dir = tmp_path / 'project'
    project_dir.mkdir()
    sys_dir = project_dir / 'sys'
    sys_dir.mkdir()
    req_dir = project_dir / 'req'
    req_dir.mkdir()

    config_file = project_dir / 'config.toml'
    config_file.write_text(
        textwrap.dedent("""
        base = "."
        [[input]]
        name = "sys_record"
        dir = "sys"
        driver = "obsidian"
        atype = "SYS"
        marker = "SYS"

        [[input]]
        name = "req_record"
        dir = "req"
        driver = "obsidian"
        atype = "REQ"
        marker = "REQ"

        [metamodel]
        filename = "project.syntagmax"
    """).strip(),
        encoding='utf-8',
    )

    metamodel_file = project_dir / 'project.syntagmax'
    metamodel_file.write_text(
        'artifact SYS:\n    id is string\n    attribute contents is mandatory string\n'
        'artifact REQ:\n    id is string\n    attribute contents is mandatory string\n',
        encoding='utf-8',
    )

    sys_md = sys_dir / 'sys.md'
    sys_md.write_text('[SYS]\nContent\n[id] OLD-SYS\n[/SYS]\n', encoding='utf-8')

    req_md = req_dir / 'req.md'
    req_md.write_text('[REQ]\nContent\n[id] OLD-REQ\n[/REQ]\n', encoding='utf-8')

    params = Params(verbose=True, render_tree=False, cwd=str(project_dir), no_git=True, output='console')
    config = Config(params, config_file)

    # Extraction
    errors = []
    artifacts = extract(config, errors)
    assert not errors
    assert len(artifacts) == 2

    # Renumbering
    renumber_artifacts(config, dry_run=False)

    # Verify records are correctly updated
    sys_content = sys_md.read_text(encoding='utf-8')
    assert '[SYS]' in sys_content

    req_content = req_md.read_text(encoding='utf-8')
    assert '[REQ]' in req_content

    # Both should be renumbered
    assert 'OLD-SYS' not in sys_content
    assert 'OLD-REQ' not in req_content
