# SPDX-License-Identifier: MIT
import logging as lg
from unittest.mock import MagicMock
import pytest

from syntagmax.analyse import ArtifactValidator, analyse_tree
from syntagmax.artifact import Artifact, Location, LineLocation, ParentLink
from syntagmax.config import Config
from syntagmax.report import CAT_SCHEMA, CAT_ATTRIBUTE, CAT_STRUCTURE


class DummyLocation(Location):
    def __init__(self, path):
        self.path = path

    def filepath(self) -> str:
        return self.path


@pytest.fixture
def dummy_config():
    cfg = MagicMock(spec=Config)
    cfg.params = {}
    return cfg


def test_validator_init_metamodel_formats(dummy_config):
    # Format 1: Metamodel with 'artifacts' and 'traces' keys
    mm1 = {'artifacts': {'REQ': {'attributes': {}}}, 'traces': {'REQ': []}}
    v1 = ArtifactValidator(mm1, {})
    assert v1._artifacts == {'REQ': {'attributes': {}}}
    assert v1._traces == {'REQ': []}

    # Format 2: Direct artifacts dict (backward compatibility / direct dict)
    mm2 = {'REQ': {'attributes': {}}}
    v2 = ArtifactValidator(mm2, {})
    assert v2._artifacts == {'REQ': {'attributes': {}}}
    assert v2._traces == {}

    # Format 3: None metamodel
    v3 = ArtifactValidator(None, {})
    assert v3._artifacts == {}
    assert v3._traces == {}


def test_make_error(dummy_config):
    validator = ArtifactValidator({}, {})
    art = Artifact(dummy_config)
    art.aid = 'REQ-1'
    art.atype = 'REQ'
    art.record = MagicMock()
    art.record.name = 'my-record'

    # With LineLocation
    art.location = LineLocation('test.md', (10, 20))
    err1 = validator._make_error(art, 'test message', CAT_SCHEMA)
    assert err1.message == 'test message'
    assert err1.category == CAT_SCHEMA
    assert err1.input_record == 'my-record'
    assert err1.artifact_id == 'REQ-1'
    assert err1.artifact_type == 'REQ'
    assert err1.file_path == 'test.md'
    assert err1.line_range == (10, 20)

    # With DummyLocation (no line range)
    art.location = DummyLocation('dummy.md')
    err2 = validator._make_error(art, 'another message', CAT_ATTRIBUTE)
    assert err2.line_range is None
    assert err2.file_path == 'dummy.md'


def test_validate_empty_metamodel(dummy_config):
    validator = ArtifactValidator(None, {})
    art = Artifact(dummy_config)
    art.aid = 'REQ-1'
    art.atype = 'REQ'
    # Should exit early and return empty errors
    assert validator.validate(art) == []


def test_validate_unknown_artifact_type(dummy_config):
    mm = {'artifacts': {'REQ': {'attributes': {}}}}
    validator = ArtifactValidator(mm, {})
    art = Artifact(dummy_config)
    art.aid = 'SYS-1'
    art.atype = 'SYS'

    errors = validator.validate(art)
    assert len(errors) == 1
    assert errors[0].category == CAT_ATTRIBUTE
    assert "Unknown artifact type: 'SYS'" in errors[0].message


def test_validate_id_schema(dummy_config):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {
                        'name': 'id',
                        'presence': 'mandatory',
                        'multiple': False,
                        'type_info': {'type': 'string'},
                        'schema': 'REQ-{num:3}',
                        'condition': None,
                    }
                }
            }
        }
    }
    validator = ArtifactValidator(mm, {})

    # Valid ID matches schema
    art_valid = Artifact(dummy_config)
    art_valid.atype = 'REQ'
    art_valid.aid = 'REQ-005'
    art_valid.fields = {'id': 'REQ-005'}
    assert len(validator.validate(art_valid)) == 0
    assert ('REQ-{num:3}', 'REQ') in validator._id_schema_cache

    # Invalid ID does not match schema
    art_invalid = Artifact(dummy_config)
    art_invalid.atype = 'REQ'
    art_invalid.aid = 'REQ-5'
    art_invalid.fields = {'id': 'REQ-5'}
    validator.errors = []
    errors = validator.validate(art_invalid)
    assert len(errors) == 1
    assert errors[0].category == CAT_SCHEMA
    assert "Artifact ID 'REQ-5' does not match schema 'REQ-{num:3}' for type 'REQ'" in errors[0].message


def test_validate_id_schema_with_condition(dummy_config):
    # Rule with condition: only validate if 'draft' attribute is not true
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {
                        'name': 'id',
                        'presence': 'mandatory',
                        'multiple': False,
                        'type_info': {'type': 'string'},
                        'schema': 'REQ-{num:3}',
                        'condition': {'anchor': 'draft', 'negated': True},
                    },
                    'draft': {'name': 'draft', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'boolean'}},
                }
            }
        }
    }
    validator = ArtifactValidator(mm, {})

    # Condition ('draft' is negated-true, so if 'draft' is True we do NOT validate id)
    # ID is 'REQ-5' (which does NOT match REQ-{num:3}), but we skip ID validation!
    # Note: we do not include 'id' in fields to prevent 'id is not allowed' checks when the rule is inactive.
    art = Artifact(dummy_config)
    art.atype = 'REQ'
    art.aid = 'REQ-5'
    art.fields = {'draft': True}
    assert len(validator.validate(art)) == 0

    # 'draft' is False, so we DO validate id, which fails.
    art2 = Artifact(dummy_config)
    art2.atype = 'REQ'
    art2.aid = 'REQ-5'
    art2.fields = {'draft': False}
    validator.errors = []
    errors = validator.validate(art2)
    assert len(errors) == 2
    assert any(e.category == CAT_ATTRIBUTE and "Missing mandatory attribute: 'id'" in e.message for e in errors)
    assert any(e.category == CAT_SCHEMA and "Artifact ID 'REQ-5' does not match schema 'REQ-{num:3}'" in e.message for e in errors)


def test_validate_attributes_extra_and_mandatory(dummy_config):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None},
                    'mandatory_attr': {'name': 'mandatory_attr', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}},
                    'optional_attr': {'name': 'optional_attr', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'string'}},
                }
            }
        }
    }
    validator = ArtifactValidator(mm, {})

    # Missing mandatory attribute
    art = Artifact(dummy_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    art.fields = {'id': 'REQ-1', 'optional_attr': 'hello'}
    errors = validator.validate(art)
    assert any("Missing mandatory attribute: 'mandatory_attr'" in e.message for e in errors)

    # Extra attribute not allowed
    art2 = Artifact(dummy_config)
    art2.atype = 'REQ'
    art2.aid = 'REQ-2'
    art2.fields = {'id': 'REQ-2', 'mandatory_attr': 'val', 'forbidden_attr': 'oops'}
    validator.errors = []
    errors2 = validator.validate(art2)
    assert any("Attribute 'forbidden_attr' is not allowed for artifact 'REQ'" in e.message for e in errors2)


def test_validate_attribute_types_multiplicity(dummy_config):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None},
                    'list_attr': {'name': 'list_attr', 'presence': 'optional', 'multiple': True, 'type_info': {'type': 'string'}},
                    'single_attr': {'name': 'single_attr', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'string'}},
                }
            }
        }
    }
    validator = ArtifactValidator(mm, {})

    # list_attr expects a list but gets a string
    art = Artifact(dummy_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    art.fields = {'id': 'REQ-1', 'list_attr': 'not-a-list'}
    errors = validator.validate(art)
    assert any("Attribute 'list_attr' must be a list (multiple=True)" in e.message for e in errors)

    # single_attr expects a string/non-list but gets a list
    art2 = Artifact(dummy_config)
    art2.atype = 'REQ'
    art2.aid = 'REQ-2'
    art2.fields = {'id': 'REQ-2', 'single_attr': ['a', 'b']}
    validator.errors = []
    errors2 = validator.validate(art2)
    assert any("Attribute 'single_attr' must not be a list (multiple=False)" in e.message for e in errors2)


def test_validate_attribute_type_integer(dummy_config):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None},
                    'int_attr': {'name': 'int_attr', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'integer'}},
                }
            }
        }
    }
    validator = ArtifactValidator(mm, {})

    # Valid integer
    art = Artifact(dummy_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    art.fields = {'id': 'REQ-1', 'int_attr': '123'}
    assert len(validator.validate(art)) == 0

    # Invalid integer
    art2 = Artifact(dummy_config)
    art2.atype = 'REQ'
    art2.aid = 'REQ-2'
    art2.fields = {'id': 'REQ-2', 'int_attr': 'abc'}
    validator.errors = []
    errors = validator.validate(art2)
    assert any("Attribute 'int_attr' value 'abc' cannot be converted to an integer" in e.message for e in errors)


def test_validate_attribute_type_boolean(dummy_config):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None},
                    'bool_default': {'name': 'bool_default', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'boolean'}},
                    'bool_custom': {
                        'name': 'bool_custom',
                        'presence': 'optional',
                        'multiple': False,
                        'type_info': {'type': 'boolean', 'custom_values': {'true': ['yes', 'da'], 'false': ['no', 'net']}},
                    },
                }
            }
        }
    }
    validator = ArtifactValidator(mm, {})

    # Valid default boolean
    art1 = Artifact(dummy_config)
    art1.atype = 'REQ'
    art1.aid = 'REQ-1'
    art1.fields = {'id': 'REQ-1', 'bool_default': 'yes'}
    assert len(validator.validate(art1)) == 0

    # Invalid default boolean
    art2 = Artifact(dummy_config)
    art2.atype = 'REQ'
    art2.aid = 'REQ-2'
    art2.fields = {'id': 'REQ-2', 'bool_default': 'maybe'}
    validator.errors = []
    errors = validator.validate(art2)
    assert any("Attribute 'bool_default' value 'maybe' is not a valid boolean" in e.message for e in errors)

    # Valid custom boolean
    art3 = Artifact(dummy_config)
    art3.atype = 'REQ'
    art3.aid = 'REQ-3'
    art3.fields = {'id': 'REQ-3', 'bool_custom': 'da'}
    validator.errors = []
    assert len(validator.validate(art3)) == 0

    # Invalid custom boolean
    art4 = Artifact(dummy_config)
    art4.atype = 'REQ'
    art4.aid = 'REQ-4'
    art4.fields = {'id': 'REQ-4', 'bool_custom': 'true'}  # 'true' is not in ['yes', 'da'] / ['no', 'net']
    validator.errors = []
    errors = validator.validate(art4)
    assert any("Attribute 'bool_custom' value 'true' is not a valid boolean" in e.message for e in errors)


def test_validate_attribute_type_enum(dummy_config):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None},
                    'enum_attr': {'name': 'enum_attr', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'enum', 'allowed': ['high', 'low']}},
                }
            }
        }
    }
    validator = ArtifactValidator(mm, {})

    # Valid enum
    art1 = Artifact(dummy_config)
    art1.atype = 'REQ'
    art1.aid = 'REQ-1'
    art1.fields = {'id': 'REQ-1', 'enum_attr': 'high'}
    assert len(validator.validate(art1)) == 0

    # Invalid enum
    art2 = Artifact(dummy_config)
    art2.atype = 'REQ'
    art2.aid = 'REQ-2'
    art2.fields = {'id': 'REQ-2', 'enum_attr': 'medium'}
    validator.errors = []
    errors = validator.validate(art2)
    assert any("Attribute 'enum_attr' value 'medium' is invalid. Allowed values: ['high', 'low']" in e.message for e in errors)


def test_validate_attribute_type_reference(dummy_config):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None},
                    'ref_attr': {'name': 'ref_attr', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'reference'}},
                }
            },
            'SYS': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None}
                }
            },
        }
    }

    # Prepare maps
    parent_art = Artifact(dummy_config)
    parent_art.aid = 'SYS-101'
    parent_art.atype = 'SYS'

    parent_bad_type = Artifact(dummy_config)
    parent_bad_type.aid = 'SYS-202'
    parent_bad_type.atype = 'UNKNOWN_TYPE'

    artifacts_map = {
        'SYS-101': parent_art,
        'SYS-202': parent_bad_type,
    }

    validator = ArtifactValidator(mm, artifacts_map)

    # 1. Valid reference
    art1 = Artifact(dummy_config)
    art1.atype = 'REQ'
    art1.aid = 'REQ-1'
    art1.fields = {'id': 'REQ-1', 'ref_attr': 'SYS-101'}
    assert len(validator.validate(art1)) == 0

    # 2. Valid reference with revision specified (@rev)
    art1_rev = Artifact(dummy_config)
    art1_rev.atype = 'REQ'
    art1_rev.aid = 'REQ-1'
    art1_rev.fields = {'id': 'REQ-1', 'ref_attr': 'SYS-101@v1.0'}
    validator.errors = []
    assert len(validator.validate(art1_rev)) == 0

    # 3. Reference is not a string
    art2 = Artifact(dummy_config)
    art2.atype = 'REQ'
    art2.aid = 'REQ-2'
    art2.fields = {'id': 'REQ-2', 'ref_attr': 123}
    validator.errors = []
    errors = validator.validate(art2)
    assert any('is a malformed reference' in e.message for e in errors)

    # 4. Unknown target ID
    art3 = Artifact(dummy_config)
    art3.atype = 'REQ'
    art3.aid = 'REQ-3'
    art3.fields = {'id': 'REQ-3', 'ref_attr': 'SYS-999'}
    validator.errors = []
    errors = validator.validate(art3)
    assert any("refers to an unknown artifact ID 'SYS-999'" in e.message for e in errors)

    # 5. Target exists but its type is not in metamodel
    art4 = Artifact(dummy_config)
    art4.atype = 'REQ'
    art4.aid = 'REQ-4'
    art4.fields = {'id': 'REQ-4', 'ref_attr': 'SYS-202'}
    validator.errors = []
    errors = validator.validate(art4)
    assert any("refers to an artifact with unknown type 'UNKNOWN_TYPE'" in e.message for e in errors)


def test_validate_reference_suppress_tracing(dummy_config, caplog):
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None},
                    'ref_attr': {'name': 'ref_attr', 'presence': 'optional', 'multiple': False, 'type_info': {'type': 'reference'}},
                }
            }
        }
    }
    # With suppress_tracing=True
    validator = ArtifactValidator(mm, {}, suppress_tracing=True)

    art = Artifact(dummy_config)
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    art.fields = {'id': 'REQ-1', 'ref_attr': 'SYS-999'}  # Unknown target

    with caplog.at_level(lg.WARNING):
        errors = validator.validate(art)
    # The error should not be in validator.errors, but rather logged as a warning
    assert len(errors) == 0
    assert any("refers to an unknown artifact ID 'SYS-999'" in r.message for r in caplog.records)


def test_validate_traces_modes_and_mandatory(dummy_config):
    # Rule definitions:
    # REQ target of SYS is mandatory and by default 'timestamp' mode
    # TEST target of REQ is mandatory 'commit' mode
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None}
                }
            },
            'SYS': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None}
                }
            },
            'TEST': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None}
                }
            },
        },
        'traces': {
            'REQ': [{'targets': ['SYS'], 'presence': 'mandatory', 'mode': 'timestamp'}],
            'TEST': [{'targets': ['REQ'], 'presence': 'mandatory', 'mode': 'commit'}],
        },
    }

    sys1 = Artifact(dummy_config)
    sys1.aid = 'SYS-1'
    sys1.atype = 'SYS'

    req1 = Artifact(dummy_config)
    req1.aid = 'REQ-1'
    req1.atype = 'REQ'

    artifacts_map = {'SYS-1': sys1, 'REQ-1': req1}

    validator = ArtifactValidator(mm, artifacts_map)

    # Case A: REQ-1 (timestamp mode trace) with normal parent link.
    # Correct timestamp mode link (None nominal revision)
    art_req_ok = Artifact(dummy_config)
    art_req_ok.aid = 'REQ-2'
    art_req_ok.atype = 'REQ'
    art_req_ok.fields = {'id': 'REQ-2'}
    art_req_ok.pids = ['SYS-1']
    art_req_ok.parent_links = [ParentLink('SYS-1', nominal_revision=None)]
    assert len(validator.validate(art_req_ok)) == 0

    # Incorrect timestamp mode link (has explicit version tag, e.g. 'v1.0')
    art_req_bad = Artifact(dummy_config)
    art_req_bad.aid = 'REQ-3'
    art_req_bad.atype = 'REQ'
    art_req_bad.fields = {'id': 'REQ-3'}
    art_req_bad.pids = ['SYS-1']
    art_req_bad.parent_links = [ParentLink('SYS-1', nominal_revision='v1.0')]
    validator.errors = []
    errors = validator.validate(art_req_bad)
    assert any("is 'by timestamp', but revision was specified: 'SYS-1@v1.0'" in e.message for e in errors)

    # Case B: TEST (commit mode trace)
    # Correct commit mode trace (has explicit revision specified)
    art_test_ok = Artifact(dummy_config)
    art_test_ok.aid = 'TEST-1'
    art_test_ok.atype = 'TEST'
    art_test_ok.fields = {'id': 'TEST-1'}
    art_test_ok.pids = ['REQ-1']
    art_test_ok.parent_links = [ParentLink('REQ-1', nominal_revision='abcdef')]
    validator.errors = []
    assert len(validator.validate(art_test_ok)) == 0

    # Incorrect commit mode trace (no revision, or revision is 'older')
    art_test_bad1 = Artifact(dummy_config)
    art_test_bad1.aid = 'TEST-2'
    art_test_bad1.atype = 'TEST'
    art_test_bad1.fields = {'id': 'TEST-2'}
    art_test_bad1.pids = ['REQ-1']
    art_test_bad1.parent_links = [ParentLink('REQ-1', nominal_revision=None)]
    validator.errors = []
    errors2 = validator.validate(art_test_bad1)
    assert any("is 'by commit', but no revision was specified for parent 'REQ-1'" in e.message for e in errors2)

    art_test_bad2 = Artifact(dummy_config)
    art_test_bad2.aid = 'TEST-3'
    art_test_bad2.atype = 'TEST'
    art_test_bad2.fields = {'id': 'TEST-3'}
    art_test_bad2.pids = ['REQ-1']
    art_test_bad2.parent_links = [ParentLink('REQ-1', nominal_revision='older')]
    validator.errors = []
    errors3 = validator.validate(art_test_bad2)
    assert any("is 'by commit', but no revision was specified for parent 'REQ-1'" in e.message for e in errors3)


def test_analyse_tree(dummy_config):
    # Setup standard test scenario
    mm = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None}
                }
            },
            'ROOT': {
                'attributes': {
                    'id': {'name': 'id', 'presence': 'mandatory', 'multiple': False, 'type_info': {'type': 'string'}, 'schema': None, 'condition': None}
                }
            },
        }
    }
    dummy_config.metamodel = mm

    root_art = Artifact(dummy_config)
    root_art.aid = 'ROOT'
    root_art.atype = 'ROOT'
    root_art.fields = {'id': 'ROOT'}

    req1 = Artifact(dummy_config)
    req1.aid = 'REQ-1'
    req1.atype = 'REQ'
    req1.fields = {'id': 'REQ-1'}

    artifacts = {'ROOT': root_art, 'REQ-1': req1}

    # Case A: exactly one ROOT artifact. Successful.
    errors = []
    analyse_tree(dummy_config, artifacts, errors)
    assert len(errors) == 0

    # Case B: zero ROOT artifacts. Fails.
    errors_b = []
    req1_map = {'REQ-1': req1}
    analyse_tree(dummy_config, req1_map, errors_b)
    assert len(errors_b) == 1
    assert errors_b[0].category == CAT_STRUCTURE
    assert 'Must have exactly one root artifact' in errors_b[0].message

    # Case C: two ROOT artifacts. Fails.
    root_art2 = Artifact(dummy_config)
    root_art2.aid = 'ROOT2'
    root_art2.atype = 'ROOT'
    root_art2.fields = {'id': 'ROOT2'}
    errors_c = []
    analyse_tree(dummy_config, {'ROOT': root_art, 'ROOT2': root_art2, 'REQ-1': req1}, errors_c)
    assert len(errors_c) == 1
    assert errors_c[0].category == CAT_STRUCTURE
    assert 'Must have exactly one root artifact' in errors_c[0].message
