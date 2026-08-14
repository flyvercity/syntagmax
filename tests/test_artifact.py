# SPDX-License-Identifier: MIT
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from syntagmax.artifact import (
    ValidationError,
    Location,
    FileLocation,
    LineLocation,
    NotebookLocation,
    Revision,
    ParentLink,
    Artifact,
    ArtifactBuilder,
    UNDEFINED_ID,
)


def test_undefined_id():
    assert UNDEFINED_ID == '<undefined>'


def test_validation_error():
    with pytest.raises(ValidationError) as exc:
        raise ValidationError('Test error')
    assert str(exc.value) == 'Test error'


def test_base_location():
    loc = Location()
    with pytest.raises(NotImplementedError):
        loc.filepath()


def test_file_location():
    # Without sidecar
    loc = FileLocation('test.md')
    assert loc.filepath() == 'test.md'
    assert str(loc) == 'test.md'

    # With sidecar
    loc_with_sidecar = FileLocation('test.md', 'test.sidecar')
    assert loc_with_sidecar.filepath() == 'test.md'
    assert str(loc_with_sidecar) == 'test.md|test.sidecar'


def test_line_location():
    loc = LineLocation('test.md', (10, 20))
    assert loc.filepath() == 'test.md'
    assert str(loc) == 'test.md:10-20'


def test_notebook_location():
    loc = NotebookLocation('test.ipynb', (5, 15), 2)
    assert loc.filepath() == 'test.ipynb'
    assert str(loc) == 'test.ipynb[2]:5-15'


def test_revision():
    dt = datetime(2025, 3, 29, 12, 0, 0)
    rev = Revision(
        hash_long='abcdef1234567890',
        hash_short='abcdef',
        timestamp=dt,
        author_email='test@example.com',
    )
    assert str(rev) == 'abcdef by test@example.com at 2025-03-29 12:00:00'


def test_parent_link():
    pl = ParentLink(pid='REQ-1')
    assert pl.pid == 'REQ-1'
    assert pl.nominal_revision is None
    assert pl.is_suspicious is False

    pl2 = ParentLink(pid='REQ-2', nominal_revision='v1.0', is_suspicious=True)
    assert pl2.pid == 'REQ-2'
    assert pl2.nominal_revision == 'v1.0'
    assert pl2.is_suspicious is True


def test_artifact_properties_and_str():
    config = MagicMock()
    art = Artifact(config)
    assert art.latest_revision is None
    assert art.contents() == '<empty>'

    # Add revisions to test latest_revision
    rev1 = Revision('hash1', 'h1', datetime(2025, 3, 29, 10, 0), 'a@ex.com')
    rev2 = Revision('hash2', 'h2', datetime(2025, 3, 29, 11, 0), 'b@ex.com')
    art.revisions.add(rev1)
    art.revisions.add(rev2)

    assert art.latest_revision == rev2

    art.fields['contents'] = 'Some actual contents'
    assert art.contents() == 'Some actual contents'

    # String representation with revision
    art.atype = 'REQ'
    art.aid = 'REQ-1'
    art.location = FileLocation('test.md')
    assert str(art) == 'REQ።REQ-1።test.md@h2'

    # String representation without revision
    art.revisions.clear()
    assert str(art) == 'REQ።REQ-1።test.md@none'


def test_artifact_builder_validation_errors():
    config = MagicMock()
    location = FileLocation('test.md')

    # Missing fields during build: No AType and no AID
    builder = ArtifactBuilder(config, Artifact, 'driver1', location)
    with pytest.raises(ValidationError) as exc:
        builder.build()
    assert 'AType is required' in str(exc.value)

    # Missing Location
    builder_no_loc = ArtifactBuilder(config, Artifact, 'driver1', None)  # type: ignore
    with pytest.raises(ValidationError) as exc:
        builder_no_loc.build()
    assert 'Location is required' in str(exc.value)

    # Set AType but missing AID
    builder.artifact.atype = 'REQ'
    with pytest.raises(ValidationError) as exc:
        builder.build()
    assert 'AID is required' in str(exc.value)


def test_artifact_builder_duplicate_id():
    config = MagicMock()
    location = FileLocation('test.md')
    builder = ArtifactBuilder(config, Artifact, 'driver1', location)
    builder.add_id('REQ-1', 'REQ')

    with pytest.raises(ValidationError) as exc:
        builder.add_id('REQ-2', 'REQ')
    assert 'Duplicate AID' in str(exc.value)


def test_artifact_builder_add_field_no_metamodel():
    config = MagicMock()
    location = FileLocation('test.md')
    builder = ArtifactBuilder(config, Artifact, 'driver1', location)
    builder.add_id('REQ-1', 'REQ')

    # Adding regular single field
    builder.add_field('title', 'My Title')
    assert builder.artifact.fields['title'] == 'My Title'

    # Adding same field again should raise ValidationError (Duplicate field)
    with pytest.raises(ValidationError) as exc:
        builder.add_field('title', 'Other Title')
    assert 'Duplicate field "title"' in str(exc.value)


def test_artifact_builder_add_field_with_metamodel_dict_rules():
    config = MagicMock()
    location = FileLocation('test.md')
    # Old/mock-style dict for backward compatibility
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'tags': {'multiple': True},
                    'title': {'multiple': False},
                    'status': {'multiple': True, 'type_info': {'type': 'enum'}},
                }
            }
        }
    }
    builder = ArtifactBuilder(config, Artifact, 'driver1', location, metamodel=metamodel)
    builder.add_id('REQ-1', 'REQ')

    # Add single field
    builder.add_field('title', 'My Title')
    assert builder.artifact.fields['title'] == 'My Title'

    # Add multiple field (which gets created as a list)
    builder.add_field('tags', 'tag1')
    builder.add_field('tags', 'tag2')
    assert builder.artifact.fields['tags'] == ['tag1', 'tag2']

    # Enum splitting on comma
    builder.add_field('status', 'draft, reviewed')
    assert builder.artifact.fields['status'] == ['draft', 'reviewed']

    # If already exists but somehow not a list, it converts (though usually it is initialized as list)
    builder.artifact.fields['tags'] = 'tag_old'
    builder.add_field('tags', 'tag_new')
    assert builder.artifact.fields['tags'] == ['tag_old', 'tag_new']


def test_artifact_builder_add_field_with_metamodel_list_rules():
    config = MagicMock()
    location = FileLocation('test.md')
    # New list-style metamodel structure
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'tags': [{'multiple': True}],
                    'title': [{'multiple': False}],
                    'status': [{'multiple': True, 'type_info': {'type': 'enum'}}],
                    'parents': [{'multiple': True, 'type_info': {'type': 'reference'}}],
                }
            }
        }
    }
    builder = ArtifactBuilder(config, Artifact, 'driver1', location, metamodel=metamodel)
    builder.add_id('REQ-1', 'REQ')

    # Reference with multiple option and comma in value splits values
    builder.add_field('parents', 'REQ-2, REQ-3')
    assert builder.artifact.fields['parents'] == ['REQ-2', 'REQ-3']

    # Enum with multiple option and comma in value splits values (inside _add_field_internal)
    builder.add_field('status', 'draft, reviewed')
    assert builder.artifact.fields['status'] == ['draft', 'reviewed']


def test_artifact_builder_build_ensures_multiple_fields_exist():
    config = MagicMock()
    location = FileLocation('test.md')
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'tags': [{'multiple': True}],
                    'title': [{'multiple': False}],
                }
            }
        }
    }
    builder = ArtifactBuilder(config, Artifact, 'driver1', location, metamodel=metamodel)
    builder.add_id('REQ-1', 'REQ')
    builder.add_field('title', 'My Req')

    artifact = builder.build()
    # "tags" was not added, but metamodel says it is multiple, so it should be initialized to []
    assert artifact.fields['tags'] == []
