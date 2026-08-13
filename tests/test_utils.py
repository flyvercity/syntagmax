from unittest.mock import patch
from syntagmax.utils import pprint


def test_pprint_mocked():
    """Test pprint by patching the Console.print method directly on the console instance in utils."""
    with patch('syntagmax.utils.console.print') as mock_print:
        pprint('Hello, world!')
        mock_print.assert_called_once_with('Hello, world!')


def test_pprint_capsys(capsys):
    """Test pprint using pytest's capsys fixture to verify standard output."""
    pprint('Test output message')
    captured = capsys.readouterr()
    assert captured.out.strip() == 'Test output message'


def test_load_config_or_exit_success(tmp_path):
    """Test load_config_or_exit loads config when file exists."""
    import tomli_w
    from syntagmax.utils import load_config_or_exit
    from syntagmax.params import Params

    config_dir = tmp_path / '.syntagmax'
    config_dir.mkdir()
    config_file = config_dir / 'config.toml'

    config_data = {'base': '..', 'input': [{'name': 'reqs', 'dir': 'requirements', 'driver': 'markdown'}]}
    config_file.write_text(tomli_w.dumps(config_data), encoding='utf-8')

    params = Params(config_file=str(config_file))
    config = load_config_or_exit(params, config_file)
    assert config is not None
    assert config.base_dir().resolve() == tmp_path.resolve()


def test_load_config_or_exit_failure(capsys):
    """Test load_config_or_exit exits with code 1 and prints error when file is missing."""
    import pytest
    from syntagmax.utils import load_config_or_exit
    from syntagmax.params import Params

    params = Params(config_file='nonexistent_config.toml')
    with pytest.raises(SystemExit) as excinfo:
        load_config_or_exit(params, 'nonexistent_config.toml')

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert 'Error: Configuration file "nonexistent_config.toml" does not exist.' in captured.out
