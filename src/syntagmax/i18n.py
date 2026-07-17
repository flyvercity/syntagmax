# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-07-16
# Description: Central i18n module for Syntagmax report localization.

import gettext
import logging
from pathlib import Path

from syntagmax.errors import FatalError

lg = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ('en', 'ru')

_LOCALE_DIR = Path(__file__).parent / 'resources' / 'locales'
_DOMAIN = 'messages'

# Active translations object — defaults to NullTranslations (English passthrough)
_translations: gettext.NullTranslations = gettext.NullTranslations()


def setup_i18n(language: str) -> gettext.NullTranslations:
    """Configure gettext translations for the specified language.

    Args:
        language: Language code ('en' or 'ru').

    Returns:
        The active translations object.

    Raises:
        FatalError: If the language code is not supported.
    """
    global _translations

    if language not in SUPPORTED_LANGUAGES:
        raise FatalError(
            f"Unsupported language '{language}'. "
            f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
        )

    if language == 'en':
        # English is the source language — use NullTranslations (passthrough)
        _translations = gettext.NullTranslations()
    else:
        try:
            _translations = gettext.translation(
                _DOMAIN,
                localedir=str(_LOCALE_DIR),
                languages=[language],
            )
        except FileNotFoundError:
            lg.warning(
                f"Translation catalog for '{language}' not found at "
                f"'{_LOCALE_DIR / language}'. Falling back to English."
            )
            _translations = gettext.NullTranslations()

    return _translations


def get_translations() -> gettext.NullTranslations:
    """Return the current translation catalog for Jinja2 environment initialization."""
    return _translations


def _(message: str) -> str:
    """Translate a message using the active translations."""
    return _translations.gettext(message)
