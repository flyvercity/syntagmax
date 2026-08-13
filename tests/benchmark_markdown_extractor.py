# SPDX-License-Identifier: MIT
import time
from unittest.mock import MagicMock
from pathlib import Path
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.markdown import MarkdownExtractor
from syntagmax.params import Params

def run_benchmark():
    # Setup dummy Config and InputRecord
    params = Params(
        verbose=False,
        render_tree=False,
        ai=False,
        cwd='.',
        no_git=True,
        allow_dirty_worktree=False,
        language='en',
        suppress_tracing=False,
    )

    cfg_file = Path('tests/config.toml')
    # If the file doesn't exist, create a temporary config file
    tmp_cfg_file = Path('/tmp/config.toml')
    if not tmp_cfg_file.exists():
        tmp_cfg_file.write_text(
            """
base = "."
[[input]]
name = "test"
dir = "."
driver = "simple-markdown"
atype = "TASK"
""",
            encoding='utf-8',
        )

    config = Config(params=params, config_filename=tmp_cfg_file)
    record = InputRecord(
        name='test',
        dir='.',
        record_base=Path('.'),
        filepaths=[],
        driver='markdown',
        default_atype='REQ',
        marker='REQ',
    )

    num_iterations = 1000
    print(f"Running baseline benchmark: initializing MarkdownExtractor {num_iterations} times...")

    start_time = time.perf_counter()
    for _ in range(num_iterations):
        _ = MarkdownExtractor(config, record)
    end_time = time.perf_counter()

    duration = end_time - start_time
    print(f"Benchmark finished in {duration:.4f} seconds.")
    return duration

if __name__ == '__main__':
    run_benchmark()
