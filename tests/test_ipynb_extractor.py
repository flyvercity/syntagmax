# SPDX-License-Identifier: MIT
import json
import pytest
from syntagmax.config import Config, InputRecord
from syntagmax.extractors.ipynb import IPynbExtractor
from syntagmax.params import Params


@pytest.fixture
def params():
    return Params(verbose=True, render_tree=False, ai=False)


@pytest.fixture
def config_file(tmp_path):
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        f"""
base = "{tmp_path.as_posix()}"
[[input]]
name = "test"
dir = "."
driver = "ipynb"
atype = "requirement"
""",
        encoding='utf-8',
    )
    return cfg_path


@pytest.fixture
def config(params, config_file):
    return Config(params=params, config_filename=config_file)


@pytest.fixture
def input_record(tmp_path):
    return InputRecord(name='test', record_base=tmp_path, filepaths=[], driver='ipynb', default_atype='requirement', marker='REQ')


def test_ipynb_extractor_basic(config, input_record, tmp_path):
    notebook_content = {
        'cells': [
            {
                'cell_type': 'markdown',
                'source': [
                    '[REQ]\n',
                    'This is cell 1 contents.\n',
                    '[id] REQ-IPY-1\n',
                    '```yaml\n',
                    'attrs:\n',
                    '  priority: high\n',
                    '```',
                ],
            },
            {'cell_type': 'code', 'source': ["print('hello world')"], 'outputs': [], 'execution_count': 1},
            {
                'cell_type': 'markdown',
                'source': [
                    '[REQ]\n',
                    'This is cell 2 contents.\n',
                    '[id] REQ-IPY-2\n',
                    '```yaml\n',
                    'attrs:\n',
                    '  priority: low\n',
                    '```',
                ],
            },
        ],
        'metadata': {},
        'nbformat': 4,
        'nbformat_minor': 4,
    }

    filepath = tmp_path / 'test.ipynb'
    filepath.write_text(json.dumps(notebook_content), encoding='utf-8')

    extractor = IPynbExtractor(config, input_record)
    artifacts, errors = extractor.extract_from_file(filepath)

    # Currently it should fail because it expects Path but gets str in IPynbExtractor
    # AND it currently only allows 1 artifact per file.

    assert len(errors) == 0
    assert len(artifacts) == 2

    assert artifacts[0].aid == 'REQ-IPY-1'
    assert artifacts[1].aid == 'REQ-IPY-2'

    # Check locations
    assert str(artifacts[0].location) == 'test.ipynb[0]:1-7'
    assert str(artifacts[1].location) == 'test.ipynb[2]:1-7'
