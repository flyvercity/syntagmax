# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import MagicMock
from benedict import benedict

from syntagmax.metrics import calculate_metrics
from syntagmax.config import Config, MetricsConfig
from syntagmax.artifact import Artifact, ArtifactMap
from syntagmax.report import ReportError, CAT_STRUCTURE


class MockInputRecord:
    def __init__(self, name: str):
        self.name = name


@pytest.fixture
def base_config():
    config = MagicMock(spec=Config)
    config.metrics = MetricsConfig(
        enabled=True,
        requirement_type='REQ',
        status_field='status',
        verify_field='verify',
        tbd_marker='TBD'
    )
    return config


def test_calculate_metrics_happy_path(base_config):
    # Setup some dummy artifacts
    artifact1 = MagicMock(spec=Artifact)
    artifact1.atype = 'REQ'
    artifact1.aid = 'REQ-001'
    artifact1.fields = {'status': 'active', 'verify': 'verified', 'contents': 'This is done.'}
    artifact1.record = MockInputRecord('reqs')

    artifact2 = MagicMock(spec=Artifact)
    artifact2.atype = 'REQ'
    artifact2.aid = 'REQ-002'
    # No verify field, status draft, contains TBD inside contents
    artifact2.fields = {'status': 'draft', 'contents': 'To be defined TBD'}
    artifact2.record = MockInputRecord('reqs')

    artifact3 = MagicMock(spec=Artifact)
    artifact3.atype = 'SYS'  # Non-requirement artifact type
    artifact3.aid = 'SYS-001'
    artifact3.fields = {'status': 'active', 'verify': 'verified', 'contents': 'System requirement'}
    artifact3.record = MockInputRecord('sys')

    artifacts: ArtifactMap = {
        'REQ-001': artifact1,
        'REQ-002': artifact2,
        'SYS-001': artifact3,
    }

    errors = []
    res = calculate_metrics(base_config, artifacts, errors)

    assert len(errors) == 0
    assert isinstance(res, benedict)
    assert res['total_requirements'] == 2
    assert res['requirements_without_verify_pct'] == 50.0
    assert res['requirements_with_tbd_pct'] == 50.0

    # Sort or check requirements_by_status
    status_by_status = res['requirements_by_status']
    assert len(status_by_status) == 2
    assert {'status': 'active', 'count': 1} in status_by_status
    assert {'status': 'draft', 'count': 1} in status_by_status


def test_calculate_metrics_custom_fields():
    config = MagicMock(spec=Config)
    config.metrics = MetricsConfig(
        enabled=True,
        requirement_type='SYS',  # Test using SYS as requirement_type
        status_field='state',   # Custom status field
        verify_field='checked', # Custom verify field
        tbd_marker='FIXME'      # Custom TBD marker
    )

    artifact1 = MagicMock(spec=Artifact)
    artifact1.atype = 'SYS'
    artifact1.aid = 'SYS-001'
    artifact1.fields = {'state': 'ready', 'checked': 'yes', 'description': 'No fixme here'}
    artifact1.record = MockInputRecord('sys')

    artifact2 = MagicMock(spec=Artifact)
    artifact2.atype = 'SYS'
    artifact2.aid = 'SYS-002'
    artifact2.fields = {'state': 'backlog', 'description': 'Must fix FIXME!'}
    artifact2.record = MockInputRecord('sys')

    artifacts: ArtifactMap = {
        'SYS-001': artifact1,
        'SYS-002': artifact2,
    }

    errors = []
    res = calculate_metrics(config, artifacts, errors)

    assert len(errors) == 0
    assert res['total_requirements'] == 2
    assert res['requirements_without_verify_pct'] == 50.0
    assert res['requirements_with_tbd_pct'] == 50.0

    status_by_status = res['requirements_by_status']
    assert len(status_by_status) == 2
    assert {'status': 'backlog', 'count': 1} in status_by_status
    assert {'status': 'ready', 'count': 1} in status_by_status


def test_calculate_metrics_filtering_by_record_name(base_config):
    artifact1 = MagicMock(spec=Artifact)
    artifact1.atype = 'REQ'
    artifact1.aid = 'REQ-001'
    artifact1.fields = {'status': 'active', 'verify': 'verified'}
    artifact1.record = MockInputRecord('record-a')

    artifact2 = MagicMock(spec=Artifact)
    artifact2.atype = 'REQ'
    artifact2.aid = 'REQ-002'
    artifact2.fields = {'status': 'draft'}
    artifact2.record = MockInputRecord('record-b')

    artifacts: ArtifactMap = {
        'REQ-001': artifact1,
        'REQ-002': artifact2,
    }

    # Filter for 'record-a' only
    errors = []
    res = calculate_metrics(base_config, artifacts, errors, filter_record_name='record-a')

    assert len(errors) == 0
    assert res['total_requirements'] == 1
    assert res['requirements_without_verify_pct'] == 0.0
    assert res['requirements_with_tbd_pct'] == 0.0
    assert res['requirements_by_status'] == [{'status': 'active', 'count': 1}]


def test_calculate_metrics_no_requirements(base_config):
    # No matching requirements at all
    artifact1 = MagicMock(spec=Artifact)
    artifact1.atype = 'SYS'
    artifact1.aid = 'SYS-001'
    artifact1.fields = {'status': 'active', 'verify': 'verified'}
    artifact1.record = MockInputRecord('sys')

    artifacts: ArtifactMap = {
        'SYS-001': artifact1,
    }

    errors = []
    res = calculate_metrics(base_config, artifacts, errors)

    # Should raise/append a ReportError and return empty benedict
    assert len(errors) == 1
    assert isinstance(errors[0], ReportError)
    assert errors[0].category == CAT_STRUCTURE
    assert errors[0].message == 'Metrics: No requirements found'
    assert res == benedict()


def test_calculate_metrics_tbd_in_list_fields(base_config):
    # Artifact can have list-valued fields (e.g. multi-value fields or list of labels/attributes)
    artifact = MagicMock(spec=Artifact)
    artifact.atype = 'REQ'
    artifact.aid = 'REQ-001'
    artifact.fields = {
        'status': 'active',
        'verify': 'verified',
        'tags': ['high-priority', 'TBD-needed', 'something-else']
    }
    artifact.record = MockInputRecord('reqs')

    artifacts: ArtifactMap = {'REQ-001': artifact}
    errors = []
    res = calculate_metrics(base_config, artifacts, errors)

    assert len(errors) == 0
    assert res['requirements_with_tbd_pct'] == 100.0


def test_calculate_metrics_unknown_status_and_missing_record(base_config):
    # Artifact with missing status field defaults to 'UNKNOWN', and can handle None record
    artifact = MagicMock(spec=Artifact)
    artifact.atype = 'REQ'
    artifact.aid = 'REQ-001'
    artifact.fields = {} # No status, no verify, no TBD
    artifact.record = None

    artifacts: ArtifactMap = {'REQ-001': artifact}
    errors = []
    res = calculate_metrics(base_config, artifacts, errors)

    assert len(errors) == 0
    assert res['total_requirements'] == 1
    assert res['requirements_by_status'] == [{'status': 'UNKNOWN', 'count': 1}]
    assert res['requirements_without_verify_pct'] == 100.0
    assert res['requirements_with_tbd_pct'] == 0.0
