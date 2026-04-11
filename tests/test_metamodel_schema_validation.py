import pytest
from syntagmax.metamodel import load_metamodel
from syntagmax.errors import FatalError


def create_metamodel(path, id_schema):
    """
    Helper to create a metamodel file with a specific id schema.
    """
    model_content = f"""
artifact REQ:
    id is string as {id_schema}
    attribute contents is mandatory string
"""
    model_file = path / 'test.model'
    model_file.write_text(model_content, encoding='utf-8')
    return model_file


@pytest.mark.parametrize(
    'invalid_schema, expected_error',
    [
        ('REQ-{invalid}', 'Invalid placeholder: {invalid}'),
        ('REQ-{num:4', 'Error loading metamodel'),
    ],
)
def test_invalid_id_schemas(tmp_path, invalid_schema, expected_error):
    """
    Verify that invalid ID schemas raise appropriate FatalError with descriptive messages.
    """
    model_file = create_metamodel(tmp_path, invalid_schema)
    errors = []

    with pytest.raises(FatalError) as excinfo:
        load_metamodel(model_file, errors)

    assert expected_error in str(excinfo.value)


@pytest.mark.parametrize(
    'valid_schema',
    [
        'REQ-{atype}-{num}',
        'REQ-{num:4}',
        '"Project REQ-{num:3}"',
    ],
)
def test_valid_id_schemas(tmp_path, valid_schema):
    """
    Verify that valid ID schemas are accepted and correctly stored in the metamodel.
    """
    model_file = create_metamodel(tmp_path, valid_schema)
    errors = []

    mm = load_metamodel(model_file, errors)

    # The stored schema should have quotes stripped if they were present
    expected = valid_schema.strip('"')
    assert mm['artifacts']['REQ']['attributes']['id'][0]['schema'] == expected
