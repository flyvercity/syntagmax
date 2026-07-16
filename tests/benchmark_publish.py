# SPDX-License-Identifier: MIT
import time
from unittest.mock import MagicMock
from syntagmax.artifact import Artifact
from syntagmax.publish import get_artifact_field_value


def run_benchmark():
    # Setup parameters
    num_artifacts = 5000
    num_fields = 100
    num_iterations = 20

    print(f'Setting up benchmark: {num_artifacts} artifacts, {num_fields} fields, running {num_iterations} iterations...')

    # Create dummy config and artifacts
    config = MagicMock()
    artifacts = []
    for i in range(num_artifacts):
        art = Artifact(config)
        art.aid = f'REQ-{i}'
        art.atype = 'REQ'
        # Populate fields
        fields = {}
        for f_idx in range(num_fields):
            fields[f'Field-{f_idx}'] = f'Value-{i}-{f_idx}'
        # Some list fields too
        fields['tags'] = [f'tag-{i}-A', f'tag-{i}-B']
        fields['empty_list'] = []
        fields['empty_str'] = ''
        art.fields = fields
        artifacts.append(art)

    # Perform lookups
    print('Running baseline benchmark...')
    start_time = time.perf_counter()

    # We do a mix of existing and non-existing lookups
    for _ in range(num_iterations):
        for art in artifacts:
            # 1. Existing lookups (normal string)
            _ = get_artifact_field_value(art, 'field-5')
            # 2. Existing lookups (list)
            _ = get_artifact_field_value(art, 'tags')
            # 3. Non-existing lookups (must iterate all fields to find None)
            _ = get_artifact_field_value(art, 'non-existent')
            # 4. Another existing lookup (case check)
            _ = get_artifact_field_value(art, 'FIELD-29')
            # 5. ID lookup (fast path)
            _ = get_artifact_field_value(art, 'id')

    end_time = time.perf_counter()
    duration = end_time - start_time
    print(f'Benchmark finished in {duration:.4f} seconds.')
    return duration


if __name__ == '__main__':
    run_benchmark()
