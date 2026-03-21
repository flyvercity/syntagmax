from syntagmax.metamodel import load_metamodel


def test_load_model_with_comments(tmp_path):
    model_content = """# Comment at the start of file
artifact MyArtifact: # comment after artifact name
    # This is a comment line
    attribute myAttr is mandatory string # comment at end of line

    # another comment after blank line
    attribute myOtherAttr is optional integer

# Comment between artifacts
artifact AnotherArtifact:
    attribute name is mandatory string
"""
    model_file = tmp_path / 'test_model.smx'
    model_file.write_text(model_content)

    errors = []
    model = load_metamodel(model_file, errors, validate=False)

    artifacts = model['artifacts']
    assert 'MyArtifact' in artifacts
    assert len(artifacts['MyArtifact']['attributes']) == 2
    assert artifacts['MyArtifact']['attributes']['myAttr']['name'] == 'myAttr'
    assert artifacts['MyArtifact']['attributes']['myOtherAttr']['name'] == 'myOtherAttr'

    assert 'AnotherArtifact' in artifacts
    assert len(artifacts['AnotherArtifact']['attributes']) == 1
    assert artifacts['AnotherArtifact']['attributes']['name']['name'] == 'name'


def test_load_model_empty_artifact(tmp_path):
    model_content = """artifact Empty:
    # only comments here
"""
    model_file = tmp_path / 'empty_model.smx'
    model_file.write_text(model_content)

    errors = []
    model = load_metamodel(model_file, errors, validate=False)
    artifacts = model['artifacts']
    assert 'Empty' in artifacts
    assert len(artifacts['Empty']['attributes']) == 0


def test_reference_type_parsing(tmp_path):
    model_content = """
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute link is optional reference
"""
    model_file = tmp_path / "test.model"
    model_file.write_text(model_content)
    errors = []
    from syntagmax.metamodel import load_metamodel
    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    assert model['artifacts']['REQ']['attributes']['link']['type_info'] == {'type': 'reference', 'to_parent': False}


def test_multiple_attribute_modifier(tmp_path):
    model_content = """
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute tags is optional multiple string
"""
    model_file = tmp_path / "test_multiple.model"
    model_file.write_text(model_content)
    errors = []
    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    assert model['artifacts']['REQ']['attributes']['tags']['multiple'] is True
    assert model['artifacts']['REQ']['attributes']['id']['multiple'] is False


def test_reference_to_parent_parsing(tmp_path):
    model_content = """
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute mainpid is mandatory reference to parent
    attribute link is optional reference
"""
    model_file = tmp_path / "test_parent.model"
    model_file.write_text(model_content)
    errors = []
    from syntagmax.metamodel import load_metamodel
    model = load_metamodel(model_file, errors, validate=False)
    assert not errors
    attrs = model['artifacts']['REQ']['attributes']
    assert attrs['mainpid']['type_info'] == {'type': 'reference', 'to_parent': True}
    assert attrs['link']['type_info'] == {'type': 'reference', 'to_parent': False}
