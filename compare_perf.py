import time
import re
from syntagmax.artifact import Artifact
from syntagmax.analyse import ArtifactValidator


class MockConfig:
    pass


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

# 1. Test optimized
start_time = time.time()
validator = ArtifactValidator(metamodel, artifacts)
for artifact in artifacts.values():
    validator.validate(artifact)
time_opt = time.time() - start_time
print(f'Optimized: {time_opt:.4f} seconds')


# 2. Test original (unoptimized)
def unoptimized_validate_id_schema(self, artifact: Artifact):
    artifact_rules = self._artifacts[artifact.atype]['attributes']
    id_rule = artifact_rules.get('id')
    if not id_rule:
        return

    schema = id_rule.get('schema')
    if not schema:
        return

    pattern = schema.replace('{atype}', artifact.atype)
    num_pattern = re.compile(r'\{num(?::(\d+))?\}')

    def replacer(match):
        padding = match.group(1)
        if padding:
            return rf'\d{{{padding}}}'
        return r'\d+'

    parts = num_pattern.split(pattern)
    regex_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            regex_parts.append(re.escape(part))
        else:
            if part:
                regex_parts.append(rf'\d{{{part}}}')
            else:
                regex_parts.append(r'\d+')

    final_pattern = ''
    last_pos = 0
    for match in num_pattern.finditer(pattern):
        final_pattern += re.escape(pattern[last_pos : match.start()])
        padding = match.group(1)
        if padding:
            final_pattern += rf'\d{{{padding}}}'
        else:
            final_pattern += r'\d+'
        last_pos = match.end()
    final_pattern += re.escape(pattern[last_pos:])
    final_pattern = f'^{final_pattern}$'

    if not re.match(final_pattern, artifact.aid):
        self.errors.append('error')


ArtifactValidator._validate_id_schema = unoptimized_validate_id_schema

start_time = time.time()
validator_orig = ArtifactValidator(metamodel, artifacts)
for artifact in artifacts.values():
    validator_orig.validate(artifact)
time_orig = time.time() - start_time
print(f'Original: {time_orig:.4f} seconds')
