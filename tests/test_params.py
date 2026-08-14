from typing import get_type_hints, get_origin, get_args, NotRequired
from syntagmax.params import VALID_LOG_LEVELS, Params


def test_valid_log_levels():
    """Verify that VALID_LOG_LEVELS contains the expected log levels."""
    expected = ('debug', 'info', 'warning', 'error', 'silent')
    assert VALID_LOG_LEVELS == expected
    assert isinstance(VALID_LOG_LEVELS, tuple)


def test_params_annotations():
    """Verify that Params TypedDict annotations are present and correctly typed."""
    hints = get_type_hints(Params, include_extras=True)

    # Check that all keys are present
    expected_keys = {
        'log_level',
        'warnings_as_errors',
        'render_tree',
        'ai',
        'cwd',
        'no_git',
        'allow_dirty_worktree',
        'language',
        'suppress_tracing',
        'tasks'
    }
    assert set(hints.keys()) == expected_keys

    # Check that NotRequired is correctly used where expected
    # The original class defines:
    # log_level: NotRequired[str]
    # warnings_as_errors: NotRequired[bool]
    # And others as standard types.

    assert get_origin(hints['log_level']) is NotRequired
    assert get_args(hints['log_level'])[0] is str

    assert get_origin(hints['warnings_as_errors']) is NotRequired
    assert get_args(hints['warnings_as_errors'])[0] is bool

    assert hints['render_tree'] is bool
    assert hints['ai'] is bool
    assert hints['cwd'] is str
    assert hints['no_git'] is bool
    assert hints['allow_dirty_worktree'] is bool
    assert hints['language'] is str
    assert hints['suppress_tracing'] is bool
    assert hints['tasks'] is bool


def test_params_required_keys():
    """Verify the __required_keys__ and __optional_keys__ behavior of Params TypedDict."""
    # Under standard Python 3.9+, TypedDict has __required_keys__ and __optional_keys__
    required = Params.__required_keys__
    optional = Params.__optional_keys__

    assert required == {
        'render_tree',
        'ai',
        'cwd',
        'no_git',
        'allow_dirty_worktree',
        'language',
        'suppress_tracing',
        'tasks'
    }
    assert optional == {
        'log_level',
        'warnings_as_errors'
    }
