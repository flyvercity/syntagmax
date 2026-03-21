from unittest.mock import MagicMock
from syntagmax.mcp.server import SyntagmaxMCPServer
from syntagmax.artifact import ARef


def test_get_artifact_content_success():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)

    mock_artifact = MagicMock()
    mock_artifact.contents.return_value = 'Line 1\nLine 2'
    server.artifacts = {ARef.coerce('SRS-001'): mock_artifact}

    # We need to access the tool function directly or via the server's tool registry
    # For now, let's assume we test the internal logic
    content = server._get_content('SRS-001')
    assert content == 'Line 1\nLine 2'


def test_get_artifact_content_not_found():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)
    server.artifacts = {}

    content = server._get_content('NON-EXISTENT')
    assert 'not found' in content.lower()
