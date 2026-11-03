from syntagmax.metamodel import load_metamodel
import textwrap


def test_load_model_with_comments(tmp_path):
    model_content = textwrap.dedent("""
        # Comment at the start of file
        artifact MyArtifact: # comment after artifact name
            # This is a comment line
            attribute myAttr is mandatory string # comment at end of line

            # another comment after blank line
            attribute myOtherAttr is optional integer

        # Comment between artifacts
        artifact AnotherArtifact:
            attribute name is mandatory string
        """)
    model_file = tmp_path / 'test_model.smx'
    model_file.write_text(model_content)

    errors = []
    model = load_metamodel(model_file, errors, validate=False)

    artifacts = model['artifacts']
    assert 'MyArtifact' in artifacts
    assert len(artifacts['MyArtifact']['attributes']) == 2
    assert artifacts['MyArtifact']['attributes']['myAttr'][0]['name'] == 'myAttr'
    assert artifacts['MyArtifact']['attributes']['myOtherAttr'][0]['type_info'] == {'type': 'integer'}

    assert 'AnotherArtifact' in artifacts
    assert len(artifacts['AnotherArtifact']['attributes']) == 1
    assert artifacts['AnotherArtifact']['attributes']['name'][0]['name'] == 'name'


def test_load_model_empty_artifact(tmp_path):
    model_content = textwrap.dedent("""
        artifact Empty:
            # only comments here
        """)
    model_file = tmp_path / 'empty_model.smx'
    model_file.write_text(model_content)

    errors = []
    model = load_metamodel(model_file, errors, validate=False)
    artifacts = model['artifacts']
    assert 'Empty' in artifacts
    assert len(artifacts['Empty']['attributes']) == 0


def test_reference_type_parsing(tmp_path):
    model_content = textwrap.dedent("""
        artifact REQ:
            attribute id is mandatory string
            attribute contents is mandatory string
            attribute link is optional reference
        """)
    model_file = tmp_path / 'test.model'
    model_file.write_text(model_content)
    errors = []
    from syntagmax.metamodel import load_metamodel

    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    assert model['artifacts']['REQ']['attributes']['link'][0]['type_info'] == {'type': 'reference', 'to_parent': False}


def test_multiple_attribute_modifier(tmp_path):
    model_content = textwrap.dedent("""
        artifact REQ:
            attribute id is mandatory string
            attribute contents is mandatory string
            attribute tags is optional multiple string
        """)
    model_file = tmp_path / 'test_multiple.model'
    model_file.write_text(model_content)
    errors = []
    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    assert model['artifacts']['REQ']['attributes']['tags'][0]['multiple'] is True
    assert model['artifacts']['REQ']['attributes']['id'][0]['multiple'] is False


def test_reference_to_parent_parsing(tmp_path):
    model_content = textwrap.dedent("""
        artifact REQ:
            attribute id is mandatory string
            attribute contents is mandatory string
            attribute mainpid is mandatory reference to parent
            attribute link is optional reference
        """)
    model_file = tmp_path / 'test_parent.model'
    model_file.write_text(model_content)
    errors = []
    from syntagmax.metamodel import load_metamodel

    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    attrs = model['artifacts']['REQ']['attributes']
    assert attrs['mainpid'][0]['type_info'] == {'type': 'reference', 'to_parent': True}
    assert attrs['link'][0]['type_info'] == {'type': 'reference', 'to_parent': False}


def test_validate_metamodel_valid():
    from syntagmax.metamodel import validate_metamodel

    metamodel = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None, 'schema': 'REQ-{num}'}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                    'is_active': [{'name': 'is_active', 'presence': 'optional', 'type_info': {'type': 'boolean'}, 'id_rule': False, 'condition': None}],
                    'extra': [{'name': 'extra', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': {'anchor': 'is_active', 'negated': False}}],
                },
            }
        },
        'traces': {
            'REQ': [
                {
                    'type': 'trace',
                    'source': 'REQ',
                    'targets': ['SPEC'],
                    'presence': 'optional',
                    'mode': 'timestamp',
                    'condition': {'anchor': 'is_active', 'negated': False},
                }
            ]
        },
    }
    errors = []
    validate_metamodel(metamodel, errors)
    assert errors == []


def test_validate_metamodel_regular_id_attribute():
    from syntagmax.metamodel import validate_metamodel

    metamodel = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel, errors)
    assert any("regular attribute named 'id'" in e for e in errors)


def test_validate_metamodel_unknown_attribute_anchor():
    from syntagmax.metamodel import validate_metamodel

    metamodel = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                    'extra': [{'name': 'extra', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': {'anchor': 'non_existent', 'negated': False}}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel, errors)
    assert any("unknown anchor 'non_existent'" in e for e in errors)


def test_validate_metamodel_invalid_attribute_anchor():
    from syntagmax.metamodel import validate_metamodel

    metamodel = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                    'string_anchor': [{'name': 'string_anchor', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                    'cond_bool_anchor': [
                        {'name': 'cond_bool_anchor', 'presence': 'optional', 'type_info': {'type': 'boolean'}, 'id_rule': False, 'condition': {'anchor': 'string_anchor', 'negated': False}}
                    ],
                    'extra1': [{'name': 'extra1', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': {'anchor': 'string_anchor', 'negated': False}}],
                    'extra2': [{'name': 'extra2', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': {'anchor': 'cond_bool_anchor', 'negated': False}}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel, errors)
    assert any("invalid anchor 'string_anchor': must be a non-conditional boolean attribute" in e for e in errors)
    assert any("invalid anchor 'cond_bool_anchor': must be a non-conditional boolean attribute" in e for e in errors)


def test_validate_metamodel_missing_and_non_mandatory_id():
    from syntagmax.metamodel import validate_metamodel

    # Missing id
    metamodel_missing = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel_missing, errors)
    assert any("missing an id attribute" in e for e in errors)

    # Id not mandatory or conditional
    metamodel_optional_id = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel_optional_id, errors)
    assert any("id attribute is not mandatory (or is conditional)" in e for e in errors)


def test_validate_metamodel_multiple_num_macros_in_id_schema():
    from syntagmax.metamodel import validate_metamodel

    metamodel = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None, 'schema': 'REQ-{num}-{num}'}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel, errors)
    assert any("multiple {num} macros (only one allowed)" in e for e in errors)


def test_validate_metamodel_missing_and_non_mandatory_contents():
    from syntagmax.metamodel import validate_metamodel

    # Missing contents
    metamodel_missing = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel_missing, errors)
    assert any("missing a contents attribute" in e for e in errors)

    # Contents not mandatory
    metamodel_optional_contents = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None}],
                    'contents': [{'name': 'contents', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                },
            }
        },
        'traces': {},
    }
    errors = []
    validate_metamodel(metamodel_optional_contents, errors)
    assert any("contents attribute is not mandatory (or is conditional)" in e for e in errors)


def test_validate_metamodel_trace_validation():
    from syntagmax.metamodel import validate_metamodel

    # Trace from unknown source atype (handled gracefully)
    metamodel_unknown_source = {
        'artifacts': {},
        'traces': {
            'UNKNOWN': [{'type': 'trace', 'source': 'UNKNOWN', 'targets': ['SPEC'], 'presence': 'optional', 'mode': 'timestamp', 'condition': {'anchor': 'some_anchor', 'negated': False}}]
        },
    }
    errors = []
    validate_metamodel(metamodel_unknown_source, errors)
    assert errors == []

    # Trace with unknown anchor
    metamodel_unknown_anchor = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                },
            }
        },
        'traces': {
            'REQ': [{'type': 'trace', 'source': 'REQ', 'targets': ['SPEC'], 'presence': 'optional', 'mode': 'timestamp', 'condition': {'anchor': 'unknown_anchor', 'negated': False}}]
        },
    }
    errors = []
    validate_metamodel(metamodel_unknown_anchor, errors)
    assert any("Trace from 'REQ' has unknown anchor 'unknown_anchor'" in e for e in errors)

    # Trace with invalid anchor (non-boolean)
    metamodel_invalid_anchor = {
        'artifacts': {
            'REQ': {
                'artifact_name': 'REQ',
                'attributes': {
                    'id': [{'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': True, 'condition': None}],
                    'contents': [{'name': 'contents', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                    'str_attr': [{'name': 'str_attr', 'presence': 'optional', 'type_info': {'type': 'string'}, 'id_rule': False, 'condition': None}],
                },
            }
        },
        'traces': {
            'REQ': [{'type': 'trace', 'source': 'REQ', 'targets': ['SPEC'], 'presence': 'optional', 'mode': 'timestamp', 'condition': {'anchor': 'str_attr', 'negated': False}}]
        },
    }
    errors = []
    validate_metamodel(metamodel_invalid_anchor, errors)
    assert any("Trace from 'REQ' has invalid anchor 'str_attr': must be a non-conditional boolean attribute" in e for e in errors)
