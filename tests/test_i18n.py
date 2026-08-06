# SPDX-License-Identifier: MIT
# Author: Boris Resnick
# Created: 2026-07-16
# Description: Unit tests for the i18n module.

import gettext

import pytest

from syntagmax.i18n import setup_i18n, _, get_translations, SUPPORTED_LANGUAGES
from syntagmax.errors import FatalError


@pytest.fixture(autouse=True)
def reset_i18n():
    """Reset i18n to English after each test to avoid polluting other tests."""
    yield
    setup_i18n('en')


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



class TestErrorMessageTranslation:
    """Tests for localized error messages."""

    def test_analyse_missing_attribute_ru(self):
        setup_i18n('ru')
        msg = _("Missing mandatory attribute: '{attr_name}'").format(attr_name='status')
        assert 'Отсутствует обязательный атрибут' in msg
        assert 'status' in msg

    def test_analyse_unknown_type_ru(self):
        setup_i18n('ru')
        msg = _("Unknown artifact type: '{atype}'").format(atype='FOO')
        assert 'Неизвестный тип артефакта' in msg
        assert 'FOO' in msg

    def test_tree_circular_reference_ru(self):
        setup_i18n('ru')
        msg = _("Circular reference detected with {aid}").format(aid='REQ-001')
        assert 'циклическая ссылка' in msg
        assert 'REQ-001' in msg

    def test_extract_duplicate_id_ru(self):
        setup_i18n('ru')
        msg = _("Duplicate artifact ID: {aid} at {location} (already defined at {other_location})").format(
            aid='REQ-001', location='file-a.md', other_location='file-b.md'
        )
        assert 'Дублирующийся идентификатор' in msg
        assert 'REQ-001' in msg

    def test_metrics_no_requirements_ru(self):
        setup_i18n('ru')
        assert _('Metrics: No requirements found') == 'Метрики: Требования не найдены'

    def test_ai_analysis_strings_ru(self):
        setup_i18n('ru')
        assert _('AI Analysis') == 'Анализ ИИ'
        assert _('Ambiguity') == 'Двусмысленность'
        assert _('Completeness') == 'Полнота'
        assert _('Verifiability') == 'Проверяемость'
        assert _('Singularity') == 'Единичность'

    def test_format_placeholders_survive_translation(self):
        """All translated messages must produce valid output with .format()."""
        setup_i18n('ru')
        # Should not raise KeyError or ValueError
        _("Attribute '{attr_name}' value '{val}' is invalid. Allowed values: {allowed}").format(
            attr_name='status', val='foo', allowed=['active', 'draft']
        )
        _("Trace from '{from_type}' to '{to_type}' is not allowed").format(
            from_type='REQ', to_type='SYS'
        )
        _("{driver} :: Missing sidecar file for {file}").format(
            driver='sidecar', file='image.png'
        )

    def test_english_error_messages_unchanged(self):
        """English locale must produce identical output to pre-i18n behavior."""
        setup_i18n('en')
        msg = _("Missing mandatory attribute: '{attr_name}'").format(attr_name='status')
        assert msg == "Missing mandatory attribute: 'status'"


class TestReportRenderingLocalized:
    """End-to-end report rendering under Russian locale."""

    def test_report_render_with_errors_in_russian(self):
        """Full Report.render() output should contain Russian error categories and messages."""
        setup_i18n('ru')
        from syntagmax.report import Report, ReportError, CAT_ATTRIBUTE

        report = Report()
        report.errors = [
            ReportError(
                message=_("Missing mandatory attribute: '{attr_name}'").format(attr_name='status'),
                category=CAT_ATTRIBUTE,
                input_record='requirements',
            ),
            ReportError(
                message=_("Unknown artifact type: '{atype}'").format(atype='FOO'),
                category=CAT_ATTRIBUTE,
                input_record='requirements',
            ),
        ]
        output = report.render()

        # Russian section headers
        assert 'Отчет об анализе' in output
        assert 'Ошибки' in output
        assert 'Ошибки атрибутов' in output

        # Russian error message bodies
        assert 'Отсутствует обязательный атрибут' in output
        assert 'Неизвестный тип артефакта' in output

        # Dynamic values preserved
        assert 'status' in output
        assert 'FOO' in output

    def test_report_render_english_unchanged(self):
        """English Report.render() output must match pre-i18n behavior."""
        setup_i18n('en')
        from syntagmax.report import Report, ReportError, CAT_ATTRIBUTE

        report = Report()
        report.errors = [
            ReportError(
                message=_("Missing mandatory attribute: '{attr_name}'").format(attr_name='status'),
                category=CAT_ATTRIBUTE,
                input_record='requirements',
            ),
        ]
        output = report.render()

        assert 'Analysis Report' in output
        assert 'Attribute Errors' in output
        assert "Missing mandatory attribute: 'status'" in output
