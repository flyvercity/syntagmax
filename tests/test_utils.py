from unittest.mock import patch
from syntagmax.utils import pprint


def test_pprint_mocked():
    """Test pprint by patching the Console.print method directly on the console instance in utils."""
    with patch("syntagmax.utils.console.print") as mock_print:
        pprint("Hello, world!")
        mock_print.assert_called_once_with("Hello, world!")


def test_pprint_capsys(capsys):
    """Test pprint using pytest's capsys fixture to verify standard output."""
    pprint("Test output message")
    captured = capsys.readouterr()
    assert captured.out.strip() == "Test output message"
