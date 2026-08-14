# SPDX-License-Identifier: MIT

"""Unit tests for syntagmax/edit.py."""

import logging as lg
from unittest.mock import MagicMock, patch


from syntagmax.artifact import UNDEFINED_ID, Artifact, FileLocation
from syntagmax.config import Config
from syntagmax.edit import (
    _generate_id,
    _is_template_id,
    _resolve_schema,
    renumber_artifacts,
)


class TestResolveSchema:
    def test_resolve_schema_aid_is_template_num(self):
        config = MagicMock(spec=Config)
        config.metamodel = None
        # aid contains {num
        schema = _resolve_schema('REQ-{num:3}', 'REQ', config)
        assert schema == 'REQ-{num:3}'

    def test_resolve_schema_aid_is_template_atype(self):
        config = MagicMock(spec=Config)
        config.metamodel = None
        # aid contains {atype}
        schema = _resolve_schema('MY-{atype}-ID', 'REQ', config)
        assert schema == 'MY-{atype}-ID'

    def test_resolve_schema_from_metamodel_dict(self):
        config = MagicMock(spec=Config)
        config.metamodel = {'artifacts': {'REQ': {'attributes': {'id': {'schema': 'MM-REQ-{num:4}'}}}}}
        schema = _resolve_schema('some-id', 'REQ', config)
        assert schema == 'MM-REQ-{num:4}'

    def test_resolve_schema_from_metamodel_list(self):
        config = MagicMock(spec=Config)
        config.metamodel = {'artifacts': {'REQ': {'attributes': {'id': [{'schema': 'MM-LIST-REQ-{num:2}'}]}}}}
        schema = _resolve_schema('', 'REQ', config)
        assert schema == 'MM-LIST-REQ-{num:2}'

    def test_resolve_schema_from_metamodel_missing_schema(self):
        config = MagicMock(spec=Config)
        config.metamodel = {'artifacts': {'REQ': {'attributes': {'id': [{'no_schema_key': 'some_value'}]}}}}
        schema = _resolve_schema('', 'REQ', config)
        assert schema == '{atype}-{num:3}'

    def test_resolve_schema_from_metamodel_not_found(self):
        config = MagicMock(spec=Config)
        config.metamodel = {'artifacts': {'SYS': {'attributes': {'id': {'schema': 'SYS-{num:2}'}}}}}
        schema = _resolve_schema('', 'REQ', config)
        assert schema == '{atype}-{num:3}'

    def test_resolve_schema_fallback_default(self):
        config = MagicMock(spec=Config)
        config.metamodel = {}
        schema = _resolve_schema('normal-id', 'REQ', config)
        assert schema == '{atype}-{num:3}'


class TestIsTemplateId:
    def test_is_template_id_none_or_empty(self):
        assert _is_template_id(None) is False
        assert _is_template_id('') is False

    def test_is_template_id_normal(self):
        assert _is_template_id('REQ-001') is False

    def test_is_template_id_contains_num(self):
        assert _is_template_id('REQ-{num:3}') is True

    def test_is_template_id_contains_atype(self):
        assert _is_template_id('PREFIX-{atype}-SUFFIX') is True


class TestGenerateId:
    def test_generate_id_with_atype_and_padding(self):
        schema = '{atype}-{num:4}'
        assert _generate_id(schema, 'REQ', 7) == 'REQ-0007'

    def test_generate_id_no_padding(self):
        schema = 'CONST-{num}'
        assert _generate_id(schema, 'SYS', 42) == 'CONST-42'

    def test_generate_id_does_not_truncate_overflow(self):
        schema = '{atype}-{num:2}'
        assert _generate_id(schema, 'REQ', 1234) == 'REQ-1234'


class TestRenumberArtifacts:
    def test_extraction_errors_returns_false(self, caplog):
        config = MagicMock(spec=Config)

        def mock_extract(conf, errors):
            errors.append('Test Extraction Error')
            return []

        with patch('syntagmax.edit.extract', side_effect=mock_extract):
            with caplog.at_level(lg.ERROR):
                success = renumber_artifacts(config)
                assert success is False
                assert 'Test Extraction Error' in caplog.text

    def test_multiple_num_macros_in_schema_returns_false(self, caplog):
        config = MagicMock(spec=Config)
        config.metamodel = {}

        artifact = MagicMock(spec=Artifact)
        artifact.atype = 'REQ'
        # Since aid has multiple {num}s, resolving schema will return aid itself
        artifact.aid = '{num}-{num}'
        artifact.location = FileLocation('req.md')

        with patch('syntagmax.edit.extract', return_value=[artifact]):
            with caplog.at_level(lg.ERROR):
                success = renumber_artifacts(config)
                assert success is False
                assert 'has multiple {num} macros' in caplog.text

    def test_zero_num_macros_in_schema_skipped(self, caplog):
        config = MagicMock(spec=Config)
        config.metamodel = {'artifacts': {'REQ': {'attributes': {'id': {'schema': 'REQ-FIXED'}}}}}

        artifact = MagicMock(spec=Artifact)
        artifact.atype = 'REQ'
        artifact.aid = 'REQ-FIXED'
        artifact.location = FileLocation('req.md')

        with patch('syntagmax.edit.extract', return_value=[artifact]):
            with caplog.at_level(lg.INFO):
                success = renumber_artifacts(config)
                assert success is True
                assert 'Preserved 1 valid IDs. Renumbered 0 artifacts. Total: 1.' in caplog.text

    def test_missing_input_record_logs_error(self, caplog):
        config = MagicMock(spec=Config)
        config.metamodel = {}

        artifact = MagicMock(spec=Artifact)
        artifact.atype = 'REQ'
        artifact.aid = UNDEFINED_ID
        artifact.location = FileLocation('req.md')
        artifact.record = None  # No input record

        with patch('syntagmax.edit.extract', return_value=[artifact]):
            with caplog.at_level(lg.ERROR):
                success = renumber_artifacts(config, dry_run=False)
                assert success is True
                assert 'Could not find input record for artifacts at' in caplog.text

    def test_driver_without_update_artifacts_support_logs_warning(self, caplog):
        config = MagicMock(spec=Config)
        config.metamodel = {}

        record = MagicMock()
        record.driver = 'unsupported-driver'

        artifact = MagicMock(spec=Artifact)
        artifact.atype = 'REQ'
        artifact.aid = UNDEFINED_ID
        artifact.location = FileLocation('req.md')
        artifact.record = record

        # An extractor class without `update_artifacts`
        class DummyExtractor:
            def __init__(self, config, record, metamodel):
                pass

        with patch('syntagmax.edit.extract', return_value=[artifact]):
            with patch('syntagmax.extract.EXTRACTORS', {'unsupported-driver': DummyExtractor}):
                with caplog.at_level(lg.WARNING):
                    success = renumber_artifacts(config, dry_run=False)
                    assert success is True
                    assert 'Driver unsupported-driver does not support renumbering yet' in caplog.text

    def test_successful_bulk_update_calls_extractor(self):
        config = MagicMock(spec=Config)
        config.metamodel = {}

        record = MagicMock()
        record.driver = 'mock-driver'

        artifact = MagicMock(spec=Artifact)
        artifact.atype = 'REQ'
        artifact.aid = UNDEFINED_ID
        artifact.location = FileLocation('req.md')
        artifact.record = record

        # An extractor class with `update_artifacts`
        mock_extractor_instance = MagicMock()

        class MockExtractor:
            def __init__(self, config, record, metamodel):
                self._inst = mock_extractor_instance

            def update_artifacts(self, loc_file, updates):
                mock_extractor_instance.update_artifacts(loc_file, updates)

        with patch('syntagmax.edit.extract', return_value=[artifact]):
            with patch('syntagmax.extract.EXTRACTORS', {'mock-driver': MockExtractor}):
                success = renumber_artifacts(config, dry_run=False)
                assert success is True
                mock_extractor_instance.update_artifacts.assert_called_once()
                # Verify that updates contain (artifact, "REQ-001")
                args, _ = mock_extractor_instance.update_artifacts.call_args
                assert args[0] == 'req.md'
                assert args[1][0][0] == artifact
                assert args[1][0][1] == 'REQ-001'

    def test_renumber_artifacts_force_mode(self):
        config = MagicMock(spec=Config)
        config.metamodel = {}

        artifact1 = MagicMock(spec=Artifact)
        artifact1.atype = 'REQ'
        artifact1.aid = 'REQ-002'
        artifact1.location = FileLocation('req.md')
        artifact1.record = MagicMock()
        artifact1.record.driver = 'mock-driver'

        artifact2 = MagicMock(spec=Artifact)
        artifact2.atype = 'REQ'
        artifact2.aid = 'REQ-005'
        artifact2.location = FileLocation('req2.md')
        artifact2.record = MagicMock()
        artifact2.record.driver = 'mock-driver'

        mock_extractor_instance = MagicMock()

        class MockExtractor:
            def __init__(self, config, record, metamodel):
                self._inst = mock_extractor_instance

            def update_artifacts(self, loc_file, updates):
                mock_extractor_instance.update_artifacts(loc_file, updates)

        # In force=True, even valid matching IDs are renumbered starting from REQ-001
        with patch('syntagmax.edit.extract', return_value=[artifact1, artifact2]):
            with patch('syntagmax.extract.EXTRACTORS', {'mock-driver': MockExtractor}):
                success = renumber_artifacts(config, force=True)
                assert success is True
                assert mock_extractor_instance.update_artifacts.call_count == 2
                # Check updates
                calls = mock_extractor_instance.update_artifacts.call_args_list
                # Calls are grouped by file location: sorted by location, so req.md and req2.md
                # Since we have two files, we expect update_artifacts to be called for both files.
                assert any(c[0][0] == 'req.md' and c[0][1][0][1] == 'REQ-001' for c in calls)
                assert any(c[0][0] == 'req2.md' and c[0][1][0][1] == 'REQ-002' for c in calls)

    def test_renumber_artifacts_duplicate_ids_warning(self, caplog):
        config = MagicMock(spec=Config)
        config.metamodel = {}

        artifact1 = MagicMock(spec=Artifact)
        artifact1.atype = 'REQ'
        artifact1.aid = 'REQ-002'
        artifact1.location = FileLocation('req.md')
        artifact1.record = MagicMock()

        artifact2 = MagicMock(spec=Artifact)
        artifact2.atype = 'REQ'
        artifact2.aid = 'REQ-002'  # duplicate ID
        artifact2.location = FileLocation('req2.md')
        artifact2.record = MagicMock()

        with patch('syntagmax.edit.extract', return_value=[artifact1, artifact2]):
            with caplog.at_level(lg.WARNING):
                success = renumber_artifacts(config)
                assert success is True
                assert 'Duplicate valid IDs found: REQ-002' in caplog.text

    def test_renumber_artifacts_with_specific_atype_filter(self):
        config = MagicMock(spec=Config)
        config.metamodel = {}

        record = MagicMock()
        record.driver = 'mock-driver'

        # REQ and SYS artifacts
        artifact1 = MagicMock(spec=Artifact)
        artifact1.atype = 'REQ'
        artifact1.aid = UNDEFINED_ID
        artifact1.location = FileLocation('req.md')
        artifact1.record = record

        artifact2 = MagicMock(spec=Artifact)
        artifact2.atype = 'SYS'
        artifact2.aid = UNDEFINED_ID
        artifact2.location = FileLocation('sys.md')
        artifact2.record = record

        mock_extractor_instance = MagicMock()

        class MockExtractor:
            def __init__(self, config, record, metamodel):
                self._inst = mock_extractor_instance

            def update_artifacts(self, loc_file, updates):
                mock_extractor_instance.update_artifacts(loc_file, updates)

        # Filtering by atype="REQ"
        with patch('syntagmax.edit.extract', return_value=[artifact1, artifact2]):
            with patch('syntagmax.extract.EXTRACTORS', {'mock-driver': MockExtractor}):
                success = renumber_artifacts(config, atype='REQ')
                assert success is True
                # Only req.md (the REQ artifact) should be updated
                mock_extractor_instance.update_artifacts.assert_called_once()
                args, _ = mock_extractor_instance.update_artifacts.call_args
                assert args[0] == 'req.md'
                assert args[1][0][0] == artifact1
                assert args[1][0][1] == 'REQ-001'
