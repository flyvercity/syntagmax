# SPDX-License-Identifier: MIT
import logging as lg
from click.testing import CliRunner
from syntagmax.cli import rms


def test_warnings_mutually_exclusive():
    runner = CliRunner()
    result = runner.invoke(rms, ['--suppress-warnings', '--warnings-as-errors', 'init'])
    assert result.exit_code != 0
    assert 'Cannot specify both --suppress-warnings and --warnings-as-errors' in result.output


def test_suppress_warnings(caplog):
    @rms.command(name='trigger-warning-test-suppress')
    def trigger_warning():
        logger = lg.getLogger('syntagmax.test')
        logger.warning('WARNING: This warning should be filtered out!')
        logger.error('ERROR: This error should NOT be filtered out!')

    try:
        runner = CliRunner()
        with caplog.at_level(lg.WARNING):
            caplog.clear()
            result = runner.invoke(rms, ['--suppress-warnings', 'trigger-warning-test-suppress'])
            assert result.exit_code == 0

            messages = [r.message for r in caplog.records]
            assert any('ERROR: This error should NOT be filtered out!' in m for m in messages)
            assert not any('WARNING: This warning should be filtered out!' in m for m in messages)
    finally:
        rms.commands.pop('trigger-warning-test-suppress', None)


def test_warnings_as_errors():
    @rms.command(name='trigger-warning-test-err')
    def trigger_warning():
        logger = lg.getLogger('syntagmax.test')
        logger.warning('Treat this warning as an error!')

    try:
        runner = CliRunner()
        result = runner.invoke(rms, ['--warnings-as-errors', 'trigger-warning-test-err'])
        assert result.exit_code == 1
        assert result.exception is not None
        assert 'Treat this warning as an error!' in str(result.exception)
    finally:
        rms.commands.pop('trigger-warning-test-err', None)


def test_no_warnings_no_error_with_warnings_as_errors():
    @rms.command(name='trigger-no-warning-test')
    def trigger_no_warning():
        logger = lg.getLogger('syntagmax.test')
        logger.info('This is an info message.')

    try:
        runner = CliRunner()
        result = runner.invoke(rms, ['--warnings-as-errors', 'trigger-no-warning-test'])
        assert result.exit_code == 0
        assert result.exception is None
    finally:
        rms.commands.pop('trigger-no-warning-test', None)
