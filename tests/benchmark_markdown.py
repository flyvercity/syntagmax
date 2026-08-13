# SPDX-License-Identifier: MIT
import time
from unittest.mock import MagicMock
from pathlib import Path
from syntagmax.config import InputRecord
from syntagmax.extractors.markdown import MarkdownExtractor


def run_benchmark():
    print('Setting up MarkdownExtractor benchmark...')
    # Setup parameters
    num_iterations = 2000

    config = MagicMock()
    config.base_dir.return_value = Path('.')

    # Let's mock input record with various markers
    input_record = InputRecord(
        name='benchmark_record',
        dir='.',
        record_base=Path('.'),
        filepaths=[],
        driver='markdown',
        default_atype='REQ',
        marker='REQ',
        markers=['COM', 'NOTE', 'TODO', 'WARN', 'FIXME'],
    )

    print(f'Instantiating MarkdownExtractor {num_iterations} times...')
    start_time = time.perf_counter()

    for i in range(num_iterations):
        # We vary the marker to avoid caching from being too trivial if cached
        input_record.marker = f'REQ{i % 10}'
        # We also change input markers to simulate various configurations
        input_record.markers = [f'COM{i % 5}', f'NOTE{i % 5}', f'TODO{i % 5}']
        _ = MarkdownExtractor(config, input_record)

    end_time = time.perf_counter()
    duration = end_time - start_time
    print(f'Benchmark finished in {duration:.4f} seconds.')
    return duration


if __name__ == '__main__':
    run_benchmark()
