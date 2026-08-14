# SPDX-License-Identifier: MIT
import logging as lg
from unittest.mock import MagicMock, patch

import pytest

from syntagmax.artifact import Artifact, UNDEFINED_ID, LineLocation
from syntagmax.config import Config, InputRecord
from syntagmax.extract import extract, build_artifact_map, print_artifact
from syntagmax.report import ReportError, CAT_EXTRACTION, CAT_DUPLICATE


@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.params = {}
    config.metamodel = MagicMock()
    return config


@pytest.fixture
def mock_input_record():
    record = MagicMock(spec=InputRecord)
    record.name = "test_record"
    record.driver = "text"
    return record


def test_print_artifact(capsys):
    artifact = MagicMock(spec=Artifact)
    artifact.driver = "text"
    artifact.atype = "requirement"
    artifact.aid = "REQ-1"
    artifact.pids = ["parent-1"]

    print_artifact(artifact)

    captured = capsys.readouterr()
    assert "text" in captured.out
    assert "requirement" in captured.out
    assert "REQ-1" in captured.out
    assert "parents: 1" in captured.out


def test_extract_success(mock_config, mock_input_record):
    mock_config.input_records.return_value = [mock_input_record]

    mock_extractor = MagicMock()
    mock_artifact = MagicMock(spec=Artifact)
    mock_extractor.extract.return_value = ([mock_artifact], [])

    with patch("syntagmax.extract.EXTRACTORS", {"text": MagicMock(return_value=mock_extractor)}):
        errors = []
        artifacts = extract(mock_config, errors)

        assert artifacts == [mock_artifact]
        assert not errors


def test_extract_with_extractor_errors(mock_config, mock_input_record):
    mock_config.input_records.return_value = [mock_input_record]

    mock_extractor = MagicMock()
    mock_artifact = MagicMock(spec=Artifact)
    mock_extractor.extract.return_value = ([mock_artifact], ["Extraction failed at line 5"])

    with patch("syntagmax.extract.EXTRACTORS", {"text": MagicMock(return_value=mock_extractor)}):
        errors = []
        artifacts = extract(mock_config, errors)

        assert artifacts == [mock_artifact]
        assert len(errors) == 1
        assert isinstance(errors[0], ReportError)
        assert errors[0].message == "Extraction failed at line 5"
        assert errors[0].category == CAT_EXTRACTION
        assert errors[0].input_record == "test_record"


def test_extract_debug_logging(mock_config, mock_input_record, capsys):
    mock_config.params = {"log_level": "debug"}
    mock_config.input_records.return_value = [mock_input_record]

    mock_extractor = MagicMock()
    mock_artifact = MagicMock(spec=Artifact)
    mock_artifact.driver = "text"
    mock_artifact.atype = "requirement"
    mock_artifact.aid = "REQ-1"
    mock_artifact.pids = []
    mock_extractor.extract.return_value = ([mock_artifact], [])

    with patch("syntagmax.extract.EXTRACTORS", {"text": MagicMock(return_value=mock_extractor)}):
        errors = []
        artifacts = extract(mock_config, errors)

        assert artifacts == [mock_artifact]

        captured = capsys.readouterr()
        assert "text" in captured.out
        assert "requirement" in captured.out
        assert "REQ-1" in captured.out


def test_build_artifact_map_success():
    artifact_1 = MagicMock(spec=Artifact)
    artifact_1.aid = "REQ-1"
    artifact_1.atype = "requirement"
    artifact_1.location = LineLocation(loc_file="test.txt", loc_lines=(1, 5))
    artifact_1.record = MagicMock(spec=InputRecord)
    artifact_1.record.name = "test_record"

    artifact_2 = MagicMock(spec=Artifact)
    artifact_2.aid = "REQ-2"
    artifact_2.atype = "requirement"
    artifact_2.location = LineLocation(loc_file="test.txt", loc_lines=(6, 10))
    artifact_2.record = MagicMock(spec=InputRecord)
    artifact_2.record.name = "test_record"

    artifacts_list = [artifact_1, artifact_2]
    errors = []

    art_map = build_artifact_map(artifacts_list, errors)

    assert not errors
    assert len(art_map) == 2
    assert art_map["REQ-1"] == artifact_1
    assert art_map["REQ-2"] == artifact_2


def test_build_artifact_map_missing_or_undefined_id():
    # Test with None ID
    artifact_none = MagicMock(spec=Artifact)
    artifact_none.aid = None
    artifact_none.atype = "requirement"
    artifact_none.location = LineLocation(loc_file="test.txt", loc_lines=(1, 5))
    artifact_none.record = MagicMock(spec=InputRecord)
    artifact_none.record.name = "test_record"

    # Test with UNDEFINED_ID
    artifact_undef = MagicMock(spec=Artifact)
    artifact_undef.aid = UNDEFINED_ID
    artifact_undef.atype = "requirement"
    artifact_undef.location = LineLocation(loc_file="test.txt", loc_lines=(6, 10))
    artifact_undef.record = MagicMock(spec=InputRecord)
    artifact_undef.record.name = "test_record"

    artifacts_list = [artifact_none, artifact_undef]
    errors = []

    art_map = build_artifact_map(artifacts_list, errors)

    assert len(art_map) == 0
    assert len(errors) == 2

    assert errors[0].category == CAT_EXTRACTION
    assert "has no ID" in errors[0].message
    assert errors[0].input_record == "test_record"
    assert errors[0].file_path == "test.txt"

    assert errors[1].category == CAT_EXTRACTION
    assert "has no ID" in errors[1].message
    assert errors[1].input_record == "test_record"
    assert errors[1].file_path == "test.txt"


def test_build_artifact_map_duplicate_id():
    record = MagicMock(spec=InputRecord)
    record.name = "test_record"

    artifact_1 = MagicMock(spec=Artifact)
    artifact_1.aid = "REQ-1"
    artifact_1.atype = "requirement"
    artifact_1.location = LineLocation(loc_file="test.txt", loc_lines=(1, 5))
    artifact_1.record = record

    artifact_2 = MagicMock(spec=Artifact)
    artifact_2.aid = "REQ-1"
    artifact_2.atype = "requirement"
    artifact_2.location = LineLocation(loc_file="test.txt", loc_lines=(6, 10))
    artifact_2.record = record

    artifacts_list = [artifact_1, artifact_2]
    errors = []

    art_map = build_artifact_map(artifacts_list, errors)

    assert len(art_map) == 1
    assert art_map["REQ-1"] == artifact_1  # The first one is kept

    assert len(errors) == 1
    assert errors[0].category == CAT_DUPLICATE
    assert "Duplicate artifact ID" in errors[0].message
    assert errors[0].input_record == "test_record"
    assert errors[0].file_path == "test.txt"
    assert errors[0].artifact_id == "REQ-1"
