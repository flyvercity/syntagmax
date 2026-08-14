from unittest.mock import MagicMock

from syntagmax.config import Config
from syntagmax.artifact import Artifact, Location
from syntagmax.report import CAT_REFERENCE, CAT_STRUCTURE
from syntagmax.tree import (
    RootLocation,
    RootArtifact,
    populate_pids,
    gather_ancestors,
    build_tree,
)


class DummyLocation(Location):
    def filepath(self) -> str:
        return 'dummy_file.md'


def test_root_location_and_artifact():
    loc = RootLocation()
    assert str(loc) == '<ROOT>'

    # We can pass None or a mock config
    mock_config = MagicMock(spec=Config)
    root_art = RootArtifact(mock_config)
    assert root_art.atype == 'ROOT'
    assert root_art.aid == 'ROOT'
    assert isinstance(root_art.location, RootLocation)
    assert root_art.children == set()


def test_populate_pids_no_metamodel():
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = None

    art = Artifact(mock_config)
    art.atype = 'REQ'
    art.fields = {'parent': 'SYS-1'}

    artifacts = {'REQ-1': art}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    assert art.pids == []
    assert art.parent_links == []
    assert errors == []


def test_populate_pids_atype_not_in_metamodel():
    metamodel = {
        'artifacts': {
            'SYS': {
                'attributes': {
                    'parent': {
                        'name': 'parent',
                        'type_info': {'type': 'reference', 'to_parent': True},
                    }
                }
            }
        }
    }
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = metamodel

    art = Artifact(mock_config)
    art.atype = 'REQ'  # REQ is not defined in metamodel
    art.fields = {'parent': 'SYS-1'}

    artifacts = {'REQ-1': art}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    assert art.pids == []
    assert art.parent_links == []
    assert errors == []


def test_populate_pids_rule_not_reference_or_not_to_parent():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'non_parent_ref': {
                        'name': 'non_parent_ref',
                        'type_info': {'type': 'reference', 'to_parent': False},
                    },
                    'non_ref_attr': {
                        'name': 'non_ref_attr',
                        'type_info': {'type': 'string'},
                    },
                }
            }
        }
    }
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = metamodel

    art = Artifact(mock_config)
    art.atype = 'REQ'
    art.fields = {'non_parent_ref': 'SYS-1', 'non_ref_attr': 'hello'}

    artifacts = {'REQ-1': art}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    assert art.pids == []
    assert art.parent_links == []
    assert errors == []


def test_populate_pids_single_parent():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'parent': {
                        'name': 'parent',
                        'type_info': {'type': 'reference', 'to_parent': True},
                    }
                }
            }
        }
    }
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = metamodel
    mock_config.get_trace_mode.return_value = 'timestamp'

    art = Artifact(mock_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    art.fields = {'parent': 'SYS-1'}

    parent_art = Artifact(mock_config)
    parent_art.atype = 'SYS'
    parent_art.aid = 'SYS-1'

    artifacts = {'REQ-1': art, 'SYS-1': parent_art}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    assert art.pids == ['SYS-1']
    assert len(art.parent_links) == 1
    assert art.parent_links[0].pid == 'SYS-1'
    # trace_mode is timestamp and no revision was specified so nominal_revision gets 'older'
    assert art.parent_links[0].nominal_revision == 'older'
    assert errors == []


def test_populate_pids_multiple_parents_comma_separated():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'parents': {
                        'name': 'parents',
                        'multiple': True,
                        'type_info': {'type': 'reference', 'to_parent': True},
                    }
                }
            }
        }
    }
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = metamodel
    mock_config.get_trace_mode.return_value = 'timestamp'

    art = Artifact(mock_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    # A single string with comma-separated values
    art.fields = {'parents': 'SYS-1, SYS-2'}

    p1 = Artifact(mock_config)
    p1.atype = 'SYS'
    p1.aid = 'SYS-1'

    p2 = Artifact(mock_config)
    p2.atype = 'SYS'
    p2.aid = 'SYS-2'

    artifacts = {'REQ-1': art, 'SYS-1': p1, 'SYS-2': p2}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    assert art.pids == ['SYS-1', 'SYS-2']
    assert len(art.parent_links) == 2
    assert art.parent_links[0].pid == 'SYS-1'
    assert art.parent_links[0].nominal_revision == 'older'
    assert art.parent_links[1].pid == 'SYS-2'
    assert art.parent_links[1].nominal_revision == 'older'
    assert errors == []


def test_populate_pids_multiple_parents_list_of_strings():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'parents': {
                        'name': 'parents',
                        'multiple': True,
                        'type_info': {'type': 'reference', 'to_parent': True},
                    }
                }
            }
        }
    }
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = metamodel
    mock_config.get_trace_mode.return_value = 'timestamp'

    art = Artifact(mock_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    # Field is a list of strings (some containing comma, some non-string)
    art.fields = {'parents': ['SYS-1, SYS-2', 42]}

    p1 = Artifact(mock_config)
    p1.atype = 'SYS'
    p1.aid = 'SYS-1'

    p2 = Artifact(mock_config)
    p2.atype = 'SYS'
    p2.aid = 'SYS-2'

    artifacts = {'REQ-1': art, 'SYS-1': p1, 'SYS-2': p2}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    # SYS-1 and SYS-2 are processed from "SYS-1, SYS-2"
    # 42 will cause an error or just partition try? Let's check:
    # `actual_ref` for 42 is passed to `actual_ref.partition('@')`. Since 42 is not a string,
    # it raises an Exception, which is appended to errors.
    assert 'SYS-1' in art.pids
    assert 'SYS-2' in art.pids
    assert len(errors) == 1
    assert 'Error processing parent link' in errors[0].message
    assert errors[0].category == CAT_REFERENCE


def test_populate_pids_with_revisions_and_trace_mode():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'parents': [
                        {
                            'name': 'parents',
                            'multiple': True,
                            'type_info': {'type': 'reference', 'to_parent': True},
                        }
                    ]
                }
            }
        }
    }
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = metamodel
    # Trace mode is 'exact'
    mock_config.get_trace_mode.return_value = 'exact'

    art = Artifact(mock_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    # nominal revision specified via @
    art.fields = {'parents': 'SYS-1@rev1, SYS-2'}

    p1 = Artifact(mock_config)
    p1.atype = 'SYS'
    p1.aid = 'SYS-1'

    p2 = Artifact(mock_config)
    p2.atype = 'SYS'
    p2.aid = 'SYS-2'

    artifacts = {'REQ-1': art, 'SYS-1': p1, 'SYS-2': p2}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    assert art.pids == ['SYS-1', 'SYS-2']
    assert len(art.parent_links) == 2
    assert art.parent_links[0].pid == 'SYS-1'
    assert art.parent_links[0].nominal_revision == 'rev1'
    assert art.parent_links[1].pid == 'SYS-2'
    # Since trace mode is 'exact' and nominal revision wasn't provided, it remains None
    assert art.parent_links[1].nominal_revision is None
    assert errors == []


def test_populate_pids_conflicting_nominal_revisions():
    # If the same parent link is processed twice but with different nominal revisions,
    # a conflict error is reported. This can happen if an attribute rules definition
    # parses the same PID multiple times or if there are multiple attributes pointing to the same parent.
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'p1': {
                        'name': 'p1',
                        'type_info': {'type': 'reference', 'to_parent': True},
                    },
                    'p2': {
                        'name': 'p2',
                        'type_info': {'type': 'reference', 'to_parent': True},
                    },
                }
            }
        }
    }
    mock_config = MagicMock(spec=Config)
    mock_config.metamodel = metamodel
    mock_config.get_trace_mode.return_value = 'exact'

    mock_record = MagicMock()
    mock_record.name = 'record1'

    art = Artifact(mock_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    art.record = mock_record
    art.location = DummyLocation()
    art.fields = {'p1': 'SYS-1@revA', 'p2': 'SYS-1@revB'}

    p1 = Artifact(mock_config)
    p1.atype = 'SYS'
    p1.aid = 'SYS-1'

    artifacts = {'REQ-1': art, 'SYS-1': p1}
    errors = []
    populate_pids(mock_config, artifacts, errors)

    assert len(errors) == 1
    assert 'Conflicting nominal revisions' in errors[0].message
    assert errors[0].category == CAT_REFERENCE
    assert errors[0].input_record == 'record1'
    assert errors[0].artifact_id == 'REQ-1'
    assert errors[0].file_path == 'dummy_file.md'


def test_gather_ancestors_and_circular_reference():
    mock_config = MagicMock(spec=Config)

    a1 = Artifact(mock_config)
    a1.aid = 'A'
    a2 = Artifact(mock_config)
    a2.aid = 'B'
    a3 = Artifact(mock_config)
    a3.aid = 'C'

    # Set up circular loop: A -> B -> C -> A
    a1.children = {'B'}
    a2.children = {'C'}
    a3.children = {'A'}

    artifacts = {'A': a1, 'B': a2, 'C': a3}

    err = gather_ancestors(artifacts, 'A')
    assert err is not None
    assert 'Circular reference detected' in err


def test_build_tree_standard():
    mock_config = MagicMock(spec=Config)
    mock_config.params = {'suppress_tracing': False}

    a1 = Artifact(mock_config)
    a1.aid = 'A'
    a1.atype = 'SYS'
    a1.pids = []

    a2 = Artifact(mock_config)
    a2.aid = 'B'
    a2.atype = 'REQ'
    a2.pids = ['A']

    artifacts = {'A': a1, 'B': a2}
    errors = []
    build_tree(mock_config, artifacts, errors)

    # ROOT artifact should be added
    assert 'ROOT' in artifacts
    root = artifacts['ROOT']
    assert root.children == {'A'}
    assert a1.children == {'B'}
    assert a2.children == set()
    assert errors == []


def test_build_tree_with_suppress_tracing():
    mock_config = MagicMock(spec=Config)
    mock_config.params = {'suppress_tracing': True}

    a1 = Artifact(mock_config)
    a1.aid = 'A'
    a1.atype = 'SYS'
    a1.pids = []

    a2 = Artifact(mock_config)
    a2.aid = 'B'
    a2.atype = 'REQ'
    # B references C which is NOT in artifacts (suppressed/missing)
    a2.pids = ['C']

    artifacts = {'A': a1, 'B': a2}
    errors = []
    build_tree(mock_config, artifacts, errors)

    # With suppress_tracing = True, any artifact where none of its PIDs are in
    # the full set of artifacts is promoted to top-level, meaning they are placed under ROOT.
    root = artifacts['ROOT']
    assert 'A' in root.children
    assert 'B' in root.children
    assert errors == []


def test_build_tree_with_circular_reference_logs_error():
    mock_config = MagicMock(spec=Config)
    mock_config.params = {'suppress_tracing': False}

    a1 = Artifact(mock_config)
    a1.aid = 'A'
    a1.atype = 'REQ'
    a1.pids = ['B']

    a2 = Artifact(mock_config)
    a2.aid = 'B'
    a2.atype = 'REQ'
    a2.pids = ['A']

    artifacts = {'A': a1, 'B': a2}
    errors = []
    build_tree(mock_config, artifacts, errors)

    assert len(errors) == 1
    assert 'Circular reference detected' in errors[0].message
    assert errors[0].category == CAT_STRUCTURE
