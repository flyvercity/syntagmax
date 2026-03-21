import pytest
from syntagmax.artifact import Artifact
from syntagmax.tree import populate_pids
from syntagmax.config import Config
from syntagmax.params import Params

def test_populate_pids_from_metamodel():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'mainpid': {'name': 'mainpid', 'multiple': False, 'type_info': {'type': 'reference', 'to_parent': True}},
                    'pids': {'name': 'pids', 'multiple': True, 'type_info': {'type': 'reference', 'to_parent': True}},
                    'link': {'name': 'link', 'multiple': False, 'type_info': {'type': 'reference', 'to_parent': False}}
                }
            }
        }
    }

    class MockConfig:
        def __init__(self, mm):
            self.metamodel = mm

    config = MockConfig(metamodel)

    art = Artifact(None)
    art.atype = 'REQ'
    art.fields = {
        'mainpid': '1',
        'pids': ['2', '3'],
        'link': 'REQ-2'
    }

    artifacts = {'1': art}
    populate_pids(config, artifacts)

    expected_pids = ['1', '2', '3']
    assert len(art.pids) == 3
    for p in expected_pids:
        assert p in art.pids
    assert 'REQ-2' not in art.pids # Since link is not to_parent

