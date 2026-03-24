import time
from syntagmax.artifact import Artifact, ArtifactMap
from syntagmax.analyse import ArtifactValidator
from syntagmax.config import Config


class MockConfig:
    pass


# Create a dummy metamodel
metamodel = {
    'artifacts': {
        'REQ': {
            'attributes': {
                'id': {
                    'name': 'id',
                    'presence': 'mandatory',
                    'schema': 'REQ-{num:3}',
                    'type_info': {'type': 'string'},
                }
            }
        }
    }
}

artifacts = {}
config = MockConfig()
for i in range(100000):
    aid = f'REQ-{i:03d}'
    a = Artifact(config)
    a.aid = aid
    a.atype = 'REQ'
    a.fields = {'id': aid}
    artifacts[aid] = a

start_time = time.time()
validator = ArtifactValidator(metamodel, artifacts)
for artifact in artifacts.values():
    validator.validate(artifact)
end_time = time.time()

print(f'Validation time for 100000 artifacts: {end_time - start_time:.4f} seconds')
