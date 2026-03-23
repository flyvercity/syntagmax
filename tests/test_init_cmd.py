from pathlib import Path

from syntagmax.init_cmd import init_project, METAMODEL_CONTENT


def test_init_project_with_cwd(tmp_path: Path) -> None:
    init_project(cwd=str(tmp_path))

    syntagmax_dir = tmp_path / '.syntagmax'
    assert syntagmax_dir.exists()
    assert syntagmax_dir.is_dir()

    config_file = syntagmax_dir / 'config.toml'
    assert config_file.exists()
    assert config_file.is_file()

    metamodel_file = syntagmax_dir / 'project.syntagmax'
    assert metamodel_file.exists()
    assert metamodel_file.is_file()
    assert metamodel_file.read_text(encoding='utf-8') == METAMODEL_CONTENT


def test_init_project_without_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init_project()

    syntagmax_dir = tmp_path / '.syntagmax'
    assert syntagmax_dir.exists()
    assert syntagmax_dir.is_dir()

    config_file = syntagmax_dir / 'config.toml'
    assert config_file.exists()
    assert config_file.is_file()

    metamodel_file = syntagmax_dir / 'project.syntagmax'
    assert metamodel_file.exists()
    assert metamodel_file.is_file()
    assert metamodel_file.read_text(encoding='utf-8') == METAMODEL_CONTENT


def test_init_project_directory_exists(tmp_path: Path) -> None:
    syntagmax_dir = tmp_path / '.syntagmax'
    syntagmax_dir.mkdir()

    init_project(cwd=str(tmp_path))

    assert syntagmax_dir.exists()
    assert (syntagmax_dir / 'config.toml').exists()
    assert (syntagmax_dir / 'project.syntagmax').exists()
