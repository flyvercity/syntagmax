
import textwrap

from syntagmax.config import Config, Params
from syntagmax.edit import renumber_artifacts
from syntagmax.extract import extract

def test_independent_atype_marker(tmp_path):
    # Setup project structure
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    docs_dir = project_dir / "docs"
    docs_dir.mkdir()

    config_file = project_dir / "config.toml"
    config_file.write_text(textwrap.dedent("""
        base = "."
        [[input]]
        name = "test_sys"
        dir = "docs"
        driver = "obsidian"
        atype = "SYS"
        marker = "REQ"

        [metamodel]
        filename = "project.syntagmax"
    """).strip(), encoding="utf-8")

    metamodel_file = project_dir / "project.syntagmax"
    metamodel_file.write_text("artifact SYS:\n    id is string\n    attribute contents is mandatory string\n", encoding="utf-8")

    test_md = docs_dir / "test.md"
    test_md.write_text("[REQ]\nRequirement content.\n[id] OLD-001\n[/REQ]")

    params = Params(verbose=True, render_tree=False, cwd=str(project_dir), no_git=True)
    config = Config(params, config_file)

    # Test extraction
    errors = []
    artifacts = extract(config, errors)
    assert not errors
    assert len(artifacts) == 1
    assert artifacts[0].atype == "SYS"
    assert artifacts[0].aid == "OLD-001"
    assert artifacts[0].record.name == "test_sys"

    # Test renumbering
    renumber_artifacts(config, dry_run=False)

    # Verify file content after renumbering
    content = test_md.read_text(encoding="utf-8")
    assert "[REQ]" in content
    assert "SYS-001" in content
    assert "[/REQ]" in content

    # Re-extract and verify
    errors = []
    artifacts = extract(config, errors)
    assert not errors
    assert artifacts[0].aid == "SYS-001"
    assert artifacts[0].atype == "SYS"
