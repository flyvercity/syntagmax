from syntagmax.artifact import Artifact
from syntagmax.tree import populate_pids


def test_populate_pids_from_metamodel():
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'mainpid': {
                        'name': 'mainpid',
                        'multiple': False,
                        'type_info': {'type': 'reference', 'to_parent': True},
                    },
                    'pids': {'name': 'pids', 'multiple': True, 'type_info': {'type': 'reference', 'to_parent': True}},
                    'link': {'name': 'link', 'multiple': False, 'type_info': {'type': 'reference', 'to_parent': False}},
                }
            }
        }
    }

    class MockConfig:
        def __init__(self, mm):
            self.metamodel = mm

        def get_trace_mode(self, source_atype: str, target_atype: str) -> str:
            if not self.metamodel:
                return 'timestamp'

            traces = self.metamodel.get('traces', {}).get(source_atype, [])
            for trace in traces:
                if target_atype in trace.get('targets', []):
                    return trace.get('mode', 'timestamp')

            return 'timestamp'

    config = MockConfig(metamodel)

    art = Artifact(None)
    art.atype = 'REQ'
    art.fields = {'mainpid': '1', 'pids': ['2', '3'], 'link': 'REQ-2'}

    artifacts = {'1': art}
    errors = []
    populate_pids(config, artifacts, errors)
    expected_pids = ['1', '2', '3']
    assert len(art.pids) == 3
    for p in expected_pids:
        assert p in art.pids
    assert 'REQ-2' not in art.pids  # Since link is not to_parent

    assert len(art.parent_links) == 3
    pids_in_links = [link.pid for link in art.parent_links]
    for p in expected_pids:
        assert p in pids_in_links
