# SPDX-License-Identifier: MIT

import pytest
from pathlib import Path
from syntagmax.metamodel import load_model
from syntagmax.artifact import Artifact, ARef
from syntagmax.analyse import ArtifactValidator
from syntagmax.config import Config

@pytest.fixture
def config_file(tmp_path):
    c = tmp_path / "config.toml"
    c.write_text("""
[[input]]
name = 'test'
dir = '.'
driver = 'text'
""", encoding="utf-8")
    return c

@pytest.fixture
def config(config_file):
    # Mocking params as dict for Config
    params = {'verbose': False}
    return Config(params, config_file)

def test_trace_parsing(tmp_path):
    model_file = tmp_path / "test.model"
    model_file.write_text("""
artifact REQ:
    attribute title is mandatory string

artifact SYS:
    attribute title is mandatory string

artifact DER:
    attribute title is mandatory string

artifact TEST:
    attribute title is mandatory string

trace from REQ to SYS or DER is mandatory
trace from TEST to REQ is mandatory
trace from TEST to SRC is optional
""", encoding="utf-8")
    
    metamodel = load_model(model_file)
    assert 'REQ' in metamodel['artifacts']
    assert 'REQ' in metamodel['traces']
    assert len(metamodel['traces']['REQ']) == 1
    assert metamodel['traces']['REQ'][0]['targets'] == ['SYS', 'DER']
    assert metamodel['traces']['REQ'][0]['presence'] == 'mandatory'

def test_trace_validation(config, tmp_path):
    model_file = tmp_path / "test.model"
    model_file.write_text("""
artifact REQ:
    attribute title is mandatory string

artifact SYS:
    attribute title is mandatory string

trace from REQ to SYS is mandatory
""", encoding="utf-8")
    
    metamodel = load_model(model_file)
    
    # 1. Valid trace
    req1 = Artifact(config)
    req1.atype = 'REQ'
    req1.aid = '1'
    req1.fields = {'title': 'Req 1'}
    req1.pids = [ARef('SYS', '101')]
    
    validator = ArtifactValidator(metamodel)
    errors = validator.validate(req1)
    assert not errors

    # 2. Missing mandatory trace
    req2 = Artifact(config)
    req2.atype = 'REQ'
    req2.aid = '2'
    req2.fields = {'title': 'Req 2'}
    req2.pids = [] # No parents
    
    validator = ArtifactValidator(metamodel, errors=[])
    errors = validator.validate(req2)
    assert any("Missing mandatory trace from 'REQ' to 'SYS'" in e for e in errors)

    # 3. Forbidden undeclared trace
    req3 = Artifact(config)
    req3.atype = 'REQ'
    req3.aid = '3'
    req3.fields = {'title': 'Req 3'}
    req3.pids = [ARef('OTHER', '999')]
    
    validator = ArtifactValidator(metamodel, errors=[])
    errors = validator.validate(req3)
    assert any("Trace from 'REQ' to 'OTHER' is not allowed" in e for e in errors)

def test_no_trace_rules_forbidden_parents(config, tmp_path):
    model_file = tmp_path / "test.model"
    model_file.write_text("""
artifact REQ:
    attribute title is mandatory string
""", encoding="utf-8")
    
    metamodel = load_model(model_file)
    
    # Artifact with a parent but no trace rules in metamodel
    req = Artifact(config)
    req.atype = 'REQ'
    req.aid = '1'
    req.fields = {'title': 'Req 1'}
    req.pids = [ARef('SYS', '101')]
    
    validator = ArtifactValidator(metamodel)
    errors = validator.validate(req)
    assert any("Trace from 'REQ' to 'SYS' is not allowed" in e for e in errors)

    # ROOT is allowed
    req_root = Artifact(config)
    req_root.atype = 'REQ'
    req_root.aid = '2'
    req_root.fields = {'title': 'Req 2'}
    req_root.pids = [ARef.root()]
    
    validator = ArtifactValidator(metamodel, errors=[])
    errors = validator.validate(req_root)
    assert not errors
