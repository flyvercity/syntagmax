# SPDX-License-Identifier: MIT
import pytest
from unittest.mock import MagicMock
from syntagmax.ai_providers import AIProvider, OllamaProvider
from syntagmax.config import AIConfig


def test_ai_provider_validation_empty_string():
    config = MagicMock(spec=AIConfig)
    # Instantiate a subclass to test base validation
    provider = OllamaProvider(config)

    with pytest.raises(ValueError) as exc_info:
        provider.analyze_requirement('')
    assert str(exc_info.value) == 'requirement_text must be a non-empty string'


def test_ai_provider_validation_none():
    config = MagicMock(spec=AIConfig)
    provider = OllamaProvider(config)

    with pytest.raises(ValueError) as exc_info:
        provider.analyze_requirement(None)  # type: ignore
    assert str(exc_info.value) == 'requirement_text must be a non-empty string'


def test_ai_provider_validation_whitespace():
    config = MagicMock(spec=AIConfig)
    provider = OllamaProvider(config)

    with pytest.raises(ValueError) as exc_info:
        provider.analyze_requirement('   ')
    assert str(exc_info.value) == 'requirement_text must be a non-empty string'


def test_ai_provider_delegates_to_impl():
    config = MagicMock(spec=AIConfig)

    class DummyProvider(AIProvider):
        def _analyze_requirement_impl(self, requirement_text: str):
            return {'status': 'success', 'text': requirement_text}

    provider = DummyProvider(config)
    result = provider.analyze_requirement('Valid requirement text')
    assert result == {'status': 'success', 'text': 'Valid requirement text'}
