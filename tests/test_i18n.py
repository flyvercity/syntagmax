# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-16
# Description: Unit tests for the i18n module.

import gettext

import pytest

from syntagmax.i18n import setup_i18n, _, get_translations, SUPPORTED_LANGUAGES
from syntagmax.errors import FatalError


class TestSetupI18n:
    """Tests for setup_i18n() function."""

    def test_english_returns_null_translations(self):
        """English should use NullTranslations (passthrough)."""
        result = setup_i18n('en')
        assert isinstance(result, gettext.NullTranslations)

    def test_english_passthrough(self):
        """English strings should pass through unchanged."""
        setup_i18n('en')
        assert _('Summary') == 'Summary'
        assert _('Change Report') == 'Change Report'

    def test_russian_loads_translations(self):
        """Russian should load the compiled .mo catalog."""
        result = setup_i18n('ru')
        # Should be a GNUTranslations (or at least not a plain NullTranslations)
        assert result is not None

    def test_russian_translates_strings(self):
        """Russian catalog should translate known strings."""
        setup_i18n('ru')
        assert _('Summary') == 'Сводка'
        assert _('Change Report') == 'Отчет об изменениях'
        assert _('Repository Information') == 'Информация о репозитории'
        assert _('Added') == 'Добавлен'
        assert _('Modified') == 'Изменен'
        assert _('Removed') == 'Удален'

    def test_russian_analysis_report_strings(self):
        """Russian catalog should translate analysis report strings."""
        setup_i18n('ru')
        assert _('Analysis Report') == 'Отчет об анализе'
        assert _('Metrics') == 'Метрики'
        assert _('Impact Analysis') == 'Анализ влияния'
        assert _('AI Analysis') == 'Анализ ИИ'
        assert _('Total Requirements') == 'Всего требований'

    def test_unsupported_language_raises_error(self):
        """Unsupported language code should raise FatalError."""
        with pytest.raises(FatalError):
            setup_i18n('fr')

    def test_unsupported_language_error_message(self):
        """Error message should list supported languages."""
        with pytest.raises(FatalError) as exc_info:
            setup_i18n('de')
        error_msg = str(exc_info.value)
        assert 'de' in error_msg
        assert 'en' in error_msg
        assert 'ru' in error_msg

    def test_switch_language_back_to_english(self):
        """Switching back to English after Russian should work."""
        setup_i18n('ru')
        assert _('Summary') == 'Сводка'
        setup_i18n('en')
        assert _('Summary') == 'Summary'

    def test_unknown_string_passthrough(self):
        """Unknown strings should pass through in any locale."""
        setup_i18n('ru')
        assert _('some_unknown_string_xyz') == 'some_unknown_string_xyz'


class TestGetTranslations:
    """Tests for get_translations() function."""

    def test_returns_translations_object(self):
        """get_translations() should return the active translations."""
        setup_i18n('en')
        trans = get_translations()
        assert isinstance(trans, gettext.NullTranslations)

    def test_returns_russian_after_setup(self):
        """After setup_i18n('ru'), get_translations() should return Russian catalog."""
        setup_i18n('ru')
        trans = get_translations()
        assert trans.gettext('Summary') == 'Сводка'


class TestSupportedLanguages:
    """Tests for SUPPORTED_LANGUAGES constant."""

    def test_contains_en_and_ru(self):
        assert 'en' in SUPPORTED_LANGUAGES
        assert 'ru' in SUPPORTED_LANGUAGES

    def test_is_tuple(self):
        assert isinstance(SUPPORTED_LANGUAGES, tuple)
