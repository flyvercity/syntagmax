# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta

from syntagmax.artifact import Artifact, Revision, ParentLink
from syntagmax.config import Config, Params
from syntagmax.impact import perform_impact_analysis


class MockRevision(Revision):
    def __init__(self, hash_short, timestamp):
        super().__init__(
            hash_long=hash_short * 4, hash_short=hash_short, timestamp=timestamp, author_email='test@example.com'
        )


def test_impact_analysis_timestamp(tmp_path):
    config_path = tmp_path / 'config.toml'
    config_path.write_text(
        """
base = "."
input = []
[impact]
enabled = true
""",
        encoding='utf-8',
    )

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=False)
    config = Config(params, config_path)

    # Mock metamodel with timestamp trace
    config.metamodel = {
        'artifacts': {'REQ': {'attributes': {}}, 'SYS': {'attributes': {}}},
        'traces': {'REQ': [{'targets': ['SYS'], 'mode': 'timestamp', 'presence': 'mandatory'}]},
    }

    now = datetime.now()

    parent = Artifact(config)
    parent.aid = 'SYS-001'
    parent.atype = 'SYS'
    parent.revisions = {MockRevision('p001', now)}

    child = Artifact(config)
    child.aid = 'REQ-001'
    child.atype = 'REQ'
    child.revisions = {MockRevision('c001', now - timedelta(hours=1))}
    child.parent_links = [ParentLink(pid='SYS-001', nominal_revision='older')]

    artifacts = {'SYS-001': parent, 'REQ-001': child}

    errors = []
    # Mock is_dirty to return False
    import syntagmax.impact

    syntagmax.impact.is_dirty = lambda c: False

    impact_data = perform_impact_analysis(config, artifacts, errors)

    assert impact_data['total_suspicious'] == 1
    assert child.parent_links[0].is_suspicious is True
    assert 'p001' in impact_data['suspicious_links'][0]['actual_revision']
    assert 'test@example.com' in impact_data['suspicious_links'][0]['actual_revision']


def test_impact_analysis_commit(tmp_path):
    config_path = tmp_path / 'config.toml'
    config_path.write_text(
        """
base = "."
input = []
[impact]
enabled = true
""",
        encoding='utf-8',
    )

    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=False)
    config = Config(params, config_path)

    now = datetime.now()

    parent = Artifact(config)
    parent.aid = 'SYS-001'
    parent.atype = 'SYS'
    parent.revisions = {MockRevision('p002', now)}  # actual is p002

    child = Artifact(config)
    child.aid = 'REQ-001'
    child.atype = 'REQ'
    child.revisions = {MockRevision('c001', now)}
    child.parent_links = [ParentLink(pid='SYS-001', nominal_revision='p001')]  # nominal is p001

    artifacts = {'SYS-001': parent, 'REQ-001': child}

    errors = []
    import syntagmax.impact

    syntagmax.impact.is_dirty = lambda c: False

    impact_data = perform_impact_analysis(config, artifacts, errors)

    assert impact_data['total_suspicious'] == 1
    assert child.parent_links[0].is_suspicious is True


def test_trace_mode_validation_errors(tmp_path):
    from syntagmax.analyse import ArtifactValidator

    config_path = tmp_path / 'config.toml'
    config_path.write_text("base = '.'\ninput = []", encoding='utf-8')
    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=False)
    config = Config(params, config_path)

    # 1. timestamp trace forbids @revision
    metamodel = {
        'artifacts': {'REQ': {'attributes': {}}, 'SYS': {'attributes': {}}},
        'traces': {'REQ': [{'targets': ['SYS'], 'mode': 'timestamp', 'presence': 'mandatory'}]},
    }

    parent = Artifact(config)
    parent.aid = 'SYS-001'
    parent.atype = 'SYS'

    child = Artifact(config)
    child.aid = 'REQ-001'
    child.atype = 'REQ'
    child.pids = ['SYS-001']
    # nominal revision specified for timestamp trace
    child.parent_links = [ParentLink(pid='SYS-001', nominal_revision='some_rev')]

    artifacts = {'SYS-001': parent, 'REQ-001': child}
    errors = []
    validator = ArtifactValidator(metamodel, artifacts, errors)
    validator.validate(child)

    assert any("by timestamp', but revision was specified" in e for e in errors)

    # 2. commit trace requires @revision
    metamodel['traces']['REQ'][0]['mode'] = 'commit'
    child.parent_links = [ParentLink(pid='SYS-001', nominal_revision=None)]
    errors = []
    validator = ArtifactValidator(metamodel, artifacts, errors)
    validator.validate(child)
    assert any("by commit', but no revision was specified" in e for e in errors)
