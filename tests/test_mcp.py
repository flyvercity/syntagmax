from unittest.mock import MagicMock
from syntagmax.mcp.server import SyntagmaxMCPServer


def test_get_artifact_content_success():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)

    mock_artifact = MagicMock()
    mock_artifact.aid = "SRS-001"
    mock_artifact.atype = "SRS"
    mock_artifact.location = "SRS.md"
    mock_artifact.latest_revision = "rev1"
    mock_artifact.parent_links = []
    mock_artifact.children = set()
    mock_artifact.fields = {"contents": "Line 1\nLine 2", "title": "Test Req"}
    
    server.artifacts = {"SRS-001": mock_artifact}

    content = server._get_content("SRS-001")
    assert "# Artifact: SRS-001 (SRS)" in content
    assert "**Location**: SRS.md" in content
    assert "**Latest Revision**: rev1" in content
    assert "Line 1\nLine 2" in content
    assert "**title**: Test Req" in content


def test_get_artifact_content_not_found():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)
    server.artifacts = {}

    content = server._get_content("NON-EXISTENT")
    assert "not found" in content.lower()


def test_list_artifacts():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)

    a1 = MagicMock()
    a1.aid = "A1"
    a1.atype = "REQ"
    a1.fields = {"title": "Summary A1"}

    a2 = MagicMock()
    a2.aid = "A2"
    a2.atype = "SPEC"
    a2.fields = {}

    server.artifacts = {"A1": a1, "A2": a2, "ROOT": MagicMock()}

    result = server._list_artifacts()
    assert "# Available Artifacts" in result
    assert "**A1** (REQ): Summary A1" in result
    assert "**A2** (SPEC)" in result
    assert "ROOT" not in result


def test_search_artifacts():
    mock_config = MagicMock()
    server = SyntagmaxMCPServer(mock_config)

    a1 = MagicMock()
    a1.aid = "LOGIN-REQ"
    a1.atype = "REQ"
    a1.fields = {"description": "User must login"}

    a2 = MagicMock()
    a2.aid = "LOGOUT-REQ"
    a2.atype = "REQ"
    a2.fields = {"description": "User can logout"}

    server.artifacts = {"LOGIN-REQ": a1, "LOGOUT-REQ": a2}

    # Search by ID
    result = server._search_artifacts("LOGIN")
    assert "LOGIN-REQ" in result
    assert "LOGOUT-REQ" not in result

    # Search by field content
    result = server._search_artifacts("logout")
    assert "LOGOUT-REQ" in result
    assert "LOGIN-REQ" not in result

    # No results
    result = server._search_artifacts("missing")
    assert "No artifacts found" in result
