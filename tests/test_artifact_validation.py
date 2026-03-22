# SPDX-License-Identifier: MIT
from unittest.mock import MagicMock
from syntagmax.extract import build_artifact_map
from syntagmax.artifact import Artifact, Location

class MockLocation(Location):
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name

def test_build_artifact_map_success():
    config = MagicMock()
    a1 = Artifact(config)
    a1.aid = 'REQ-1'
    a1.atype = 'REQ'
    a1.location = MockLocation('file1.md')
    
    a2 = Artifact(config)
    a2.aid = 'REQ-2'
    a2.atype = 'REQ'
    a2.location = MockLocation('file2.md')
    
    artifacts_list = [a1, a2]
    artifact_map, errors = build_artifact_map(artifacts_list)
    
    assert len(errors) == 0
    assert len(artifact_map) == 2
    assert artifact_map['REQ-1'] == a1
    assert artifact_map['REQ-2'] == a2

def test_build_artifact_map_no_id():
    config = MagicMock()
    a1 = Artifact(config)
    a1.aid = ''
    a1.atype = 'REQ'
    a1.location = MockLocation('file1.md')
    
    artifacts_list = [a1]
    artifact_map, errors = build_artifact_map(artifacts_list)
    
    assert len(errors) == 1
    assert 'has no ID' in errors[0]
    assert 'file1.md' in errors[0]
    assert len(artifact_map) == 0

def test_build_artifact_map_duplicate_id():
    config = MagicMock()
    a1 = Artifact(config)
    a1.aid = 'REQ-1'
    a1.atype = 'REQ'
    a1.location = MockLocation('file1.md')
    
    a2 = Artifact(config)
    a2.aid = 'REQ-1'
    a2.atype = 'REQ'
    a2.location = MockLocation('file2.md')
    
    artifacts_list = [a1, a2]
    artifact_map, errors = build_artifact_map(artifacts_list)
    
    assert len(errors) == 1
    assert 'Duplicate artifact ID' in errors[0]
    assert 'REQ-1' in errors[0]
    assert 'file2.md' in errors[0]
    assert 'already defined at file1.md' in errors[0]
    assert len(artifact_map) == 1
    assert artifact_map['REQ-1'] == a1
