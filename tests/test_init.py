# SPDX-License-Identifier: MIT

import tomllib
from pathlib import Path
from syntagmax.init_cmd import generate_toml, init_project, METAMODEL_CONTENT


def test_generate_toml():
    toml_content = generate_toml()

    # Check that it's a non-empty string
    assert isinstance(toml_content, str)
    assert len(toml_content) > 0

    # Check for expected sections (some are commented by default)
    assert '[[input]]' in toml_content
    assert '[metamodel]' in toml_content
    assert 'base = ".."' in toml_content

    # Parse the TOML. Note that many fields are commented out in generate_toml().
    # Only uncommented fields will be parsed by tomllib.
    data = tomllib.loads(toml_content)

    assert data['base'] == '..'
    assert data['metamodel']['filename'] == 'project.syntagmax'
    assert len(data['input']) == 1
    assert data['input'][0]['name'] == 'requirements'
    assert data['input'][0]['dir'] == 'REQ'
    assert data['input'][0]['driver'] == 'obsidian'


def test_init_project(tmp_path):
    # Change current working directory to tmp_path or pass it to init_project
    init_project(cwd=str(tmp_path))

    syntagmax_dir = tmp_path / '.syntagmax'
    assert syntagmax_dir.is_dir()

    config_file = syntagmax_dir / 'config.toml'
    assert config_file.is_file()

    metamodel_file = syntagmax_dir / 'project.syntagmax'
    assert metamodel_file.is_file()

    # Verify content
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert '[[input]]' in content
        assert 'base = ".."' in content

    with open(metamodel_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert content == METAMODEL_CONTENT
