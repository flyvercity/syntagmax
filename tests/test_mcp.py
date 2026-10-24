from unittest.mock import MagicMock
import pytest

from syntagmax.config import Config
from syntagmax.mcp.server import SyntagmaxMCPServer
from syntagmax.params import Params


def test_get_artifact_content_success():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)

    mock_artifact = MagicMock()
    mock_artifact.aid = 'SRS-001'
    mock_artifact.atype = 'SRS'
    mock_artifact.location = 'SRS.md'
    mock_artifact.latest_revision = 'rev1'
    mock_artifact.parent_links = []
    mock_artifact.children = set()
    mock_artifact.fields = {'contents': 'Line 1\nLine 2', 'title': 'Test Req'}

    server.artifacts = {'SRS-001': mock_artifact}

    content = server._get_content('SRS-001')
    assert '# Artifact: SRS-001 (SRS)' in content
    assert '**Location**: SRS.md' in content
    assert '**Latest Revision**: rev1' in content
    assert 'Line 1\nLine 2' in content
    assert '**title**: Test Req' in content


def test_get_artifact_content_not_found():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)
    server.artifacts = {}

    content = server._get_content('NON-EXISTENT')
    assert 'not found' in content.lower()


def test_list_artifacts():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)

    a1 = MagicMock()
    a1.aid = 'A1'
    a1.atype = 'REQ'
    a1.fields = {'title': 'Summary A1'}

    a2 = MagicMock()
    a2.aid = 'A2'
    a2.atype = 'SPEC'
    a2.fields = {}

    server.artifacts = {'A1': a1, 'A2': a2, 'ROOT': MagicMock()}

    result = server._list_artifacts()
    assert '# Available Artifacts' in result
    assert '**A1** (REQ): Summary A1' in result
    assert '**A2** (SPEC)' in result
    assert 'ROOT' not in result


def test_search_artifacts():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)

    a1 = MagicMock()
    a1.aid = 'LOGIN-REQ'
    a1.atype = 'REQ'
    a1.fields = {'description': 'User must login'}

    a2 = MagicMock()
    a2.aid = 'LOGOUT-REQ'
    a2.atype = 'REQ'
    a2.fields = {'description': 'User can logout'}

    server.artifacts = {'LOGIN-REQ': a1, 'LOGOUT-REQ': a2}

    # Search by ID
    result = server._search_artifacts('LOGIN')
    assert 'LOGIN-REQ' in result
    assert 'LOGOUT-REQ' not in result

    # Search by field content
    result = server._search_artifacts('logout')
    assert 'LOGOUT-REQ' in result
    assert 'LOGIN-REQ' not in result

    # No results
    result = server._search_artifacts('missing')
    assert 'No artifacts found' in result


@pytest.fixture
def project_config(tmp_path):
    config_path = tmp_path / 'config.toml'
    config_path.write_text(
        'base = "."\n[[input]]\nname = "requirements"\ndir = "REQ"\n'
        'driver = "simple-markdown"\natype = "REQ"\n',
        encoding='utf-8',
    )
    params = Params(
        render_tree=False,
        ai=False,
        cwd=str(tmp_path),
        no_git=True,
        allow_dirty_worktree=True,
        language='en',
        suppress_tracing=False,
        tasks=False,
    )
    return Config(params=params, config_filename=config_path)


def test_create_requirement(project_config):
    server = SyntagmaxMCPServer(project_config)
    server.initialize()

    result = server._create_requirement('requirements', 'New requirement', 'The system shall respond.', {'status': 'draft'})

    assert 'Created REQ requirement "REQ-001"' in result
    assert (project_config.base_dir() / 'REQ/REQ-001.md').exists()
    assert server.artifacts['REQ-001'].fields['title'] == 'New requirement'
    assert server.artifacts['REQ-001'].fields['contents'] == 'The system shall respond.'
    assert server.artifacts['REQ-001'].fields['status'] == 'draft'

    second_result = server._create_requirement('requirements', 'Another requirement', 'The system shall also respond.')

    assert 'Created REQ requirement "REQ-002"' in second_result
    assert 'REQ-002' in server.artifacts


def test_create_requirement_in_obsidian_record(project_config):
    project_config.input_records()[0].driver = 'obsidian'
    server = SyntagmaxMCPServer(project_config)
    server.initialize()

    result = server._create_requirement('requirements', 'Obsidian requirement', 'The system shall respond.')

    assert 'Created REQ requirement "REQ-001"' in result
    assert server.artifacts['REQ-001'].fields['title'] == 'Obsidian requirement'
    assert server.artifacts['REQ-001'].fields['contents'].strip() == 'The system shall respond.'


def test_create_requirement_rejects_unsupported_driver(project_config):
    project_config.input_records()[0].driver = 'text'
    server = SyntagmaxMCPServer(project_config)

    result = server._create_requirement('requirements', 'New requirement', 'The system shall respond.')

    assert 'unsupported driver' in result
    assert not (project_config.base_dir() / 'REQ').exists()


def test_create_requirement_is_disabled_for_non_local_server(project_config):
    server = SyntagmaxMCPServer(project_config, host='0.0.0.0')

    result = server._create_requirement('requirements', 'New requirement', 'The system shall respond.')

    assert 'only available' in result
    assert not (project_config.base_dir() / 'REQ').exists()


def test_create_requirement_rolls_back_validation_errors(project_config):
    config_path = project_config._root_dir / 'config.toml'
    config_path.write_text(
        'base = "."\n[[input]]\nname = "requirements"\ndir = "REQ"\n'
        'driver = "simple-markdown"\natype = "REQ"\n'
        '[metamodel]\nfilename = "project.syntagmax"\n',
        encoding='utf-8',
    )
    (project_config._root_dir / 'project.syntagmax').write_text(
        'artifact REQ:\n'
        '    id is string\n'
        '    attribute contents is mandatory string\n'
        '    attribute title is mandatory string\n'
        '    attribute status is mandatory enum [draft, active]\n',
        encoding='utf-8',
    )
    validated_config = Config(params=project_config.params, config_filename=config_path)
    server = SyntagmaxMCPServer(validated_config)
    server.initialize()

    result = server._create_requirement('requirements', 'New requirement', 'The system shall respond.')

    assert 'Could not create requirement' in result
    assert not (validated_config.base_dir() / 'REQ/REQ-001.md').exists()
    assert 'REQ-001' not in server.artifacts


def test_create_requirement_rejects_empty_contents(project_config):
    server = SyntagmaxMCPServer(project_config)
    server.initialize()

    result = server._create_requirement('requirements', 'New requirement', '')

    assert 'must not be empty' in result
    assert not (project_config.base_dir() / 'REQ').exists()
