import time
from syntagmax.analyse import ArtifactValidator
from syntagmax.artifact import Artifact, Location

class MockConfig:
    pass

def run_benchmark():
    # Setup metamodel
    metamodel = {
        'artifacts': {
            'REQ': {
                'attributes': {
                    'title': {'name': 'title', 'presence': 'mandatory', 'type_info': {'type': 'string'}},
                    'status': {'name': 'status', 'presence': 'optional', 'type_info': {'type': 'string'}},
                    'priority': {'name': 'priority', 'presence': 'mandatory', 'type_info': {'type': 'string'}},
                    'author': {'name': 'author', 'presence': 'optional', 'type_info': {'type': 'string'}},
                    'id': {'name': 'id', 'presence': 'mandatory', 'type_info': {'type': 'string'}, 'schema': 'REQ-{num:3}'}
                }
            }
        }
    }

    # Setup artifacts map
    artifacts = {}
    config = MockConfig()
    for i in range(10000):
        aid = f'REQ-{i:03d}'
        a = Artifact(config)
        a.aid = aid
        a.atype = 'REQ'
        a.fields = {'title': 'Test', 'priority': 'High', 'id': aid}
        a.pids = []
        artifacts[aid] = a

    # Prime it
    validator = ArtifactValidator(metamodel, artifacts)
    for a in artifacts.values():
        validator.validate(a)

    start = time.perf_counter()
    for _ in range(5):
        validator = ArtifactValidator(metamodel, artifacts)
        for a in artifacts.values():
            validator.validate(a)
    end = time.perf_counter()

    print(f"Validation took {(end - start)/5:.4f} seconds per run")

if __name__ == '__main__':
    run_benchmark()
