# SPDX-License-Identifier: MIT

import json
from unittest.mock import MagicMock, patch

import pytest

from syntagmax.ai_providers import AIError, AIProvider, BedrockProvider, OllamaProvider
from syntagmax.config import AIConfig


def test_ai_provider_validation_empty_string():
    config = MagicMock(spec=AIConfig)
    provider = OllamaProvider(config)

    with pytest.raises(ValueError) as exc_info:
        provider.analyze_requirement('')
    assert str(exc_info.value) == 'requirement_text must be a non-empty string'


def test_ai_provider_validation_none():
    config = MagicMock(spec=AIConfig)
    provider = OllamaProvider(config)

    with pytest.raises(ValueError) as exc_info:
        provider.analyze_requirement(None)  # type: ignore[arg-type]
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


def test_bedrock_provider_requests_success():
    config = AIConfig(
        provider='bedrock',
        model='anthropic.claude-3-sonnet-20240229-v1:0',
        aws_region_name='us-east-1',
        aws_api_key='fake-api-key',
        timeout_s=10.0,
    )
    provider = BedrockProvider(config)

    mock_response_body = {
        'content': [
            {
                'text': json.dumps(
                    {
                        'metrics': {
                            'ambiguity': 0.1,
                            'completeness': 0.9,
                            'verifiability': 0.8,
                            'singularity': 0.95,
                        },
                        'evidence': [],
                        'questions': [],
                        'rewrite': {
                            'shall': 'The system shall do X.',
                            'acceptance_criteria': ['Criteria 1'],
                        },
                    }
                )
            }
        ]
    }

    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_body
        mock_post.return_value = mock_resp

        result = provider.analyze_requirement('The system should do X.')

        mock_post.assert_called_once()
        assert result['metrics']['ambiguity'] == 0.1
        assert result['rewrite']['shall'] == 'The system shall do X.'


def test_bedrock_provider_requests_failure():
    config = AIConfig(
        provider='bedrock',
        aws_region_name='us-east-1',
        aws_api_key='fake-api-key',
    )
    provider = BedrockProvider(config)

    with patch('requests.post') as mock_post:
        mock_post.side_effect = Exception('HTTP Error')
        with pytest.raises(AIError, match='Failed to call Bedrock via requests'):
            provider.analyze_requirement('The system should do X.')


def test_bedrock_provider_boto3_success():
    config = AIConfig(
        provider='bedrock',
        aws_access_key_id='fake-access-key',
        aws_secret_access_key='fake-secret-key',
        aws_session_token='fake-session-token',
        aws_region_name='us-east-1',
    )
    provider = BedrockProvider(config)

    mock_response_body = {
        'content': [
            {
                'text': json.dumps(
                    {
                        'metrics': {
                            'ambiguity': 0.2,
                            'completeness': 0.8,
                            'verifiability': 0.7,
                            'singularity': 0.9,
                        },
                        'evidence': [],
                        'questions': [],
                        'rewrite': {
                            'shall': 'The system shall do Y.',
                            'acceptance_criteria': [],
                        },
                    }
                )
            }
        ]
    }

    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps(mock_response_body).encode('utf-8')
    mock_client.invoke_model.return_value = {'body': mock_body}

    with patch('boto3.client', return_value=mock_client) as mock_boto:
        result = provider.analyze_requirement('The system should do Y.')

        mock_boto.assert_called_once_with(
            service_name='bedrock-runtime',
            region_name='us-east-1',
            aws_access_key_id='fake-access-key',
            aws_secret_access_key='fake-secret-key',
            aws_session_token='fake-session-token',
        )
        assert result['metrics']['ambiguity'] == 0.2


def test_sanitize_json_scenarios():
    config = MagicMock(spec=AIConfig)
    provider = OllamaProvider(config)

    # Valid simple escapes should not be altered
    assert provider._sanitize_json(r'{"text": "line1\nline2"}') == r'{"text": "line1\nline2"}'
    assert provider._sanitize_json(r'{"text": "quote\"escaped"}') == r'{"text": "quote\"escaped"}'
    assert provider._sanitize_json(r'{"text": "backslash\\escaped"}') == r'{"text": "backslash\\escaped"}'
    assert provider._sanitize_json(r'{"text": "forward\/slash"}') == r'{"text": "forward\/slash"}'
    assert provider._sanitize_json(r'{"text": "tab\tspace"}') == r'{"text": "tab\tspace"}'

    # Valid Unicode escapes should remain unchanged
    assert provider._sanitize_json(r'{"text": "unicode\u1234"}') == r'{"text": "unicode\u1234"}'
    assert provider._sanitize_json(r'{"text": "unicode\uABCD"}') == r'{"text": "unicode\uABCD"}'

    # Invalid Unicode escape (not enough digits) should have backslash escaped
    assert provider._sanitize_json(r'{"text": "unicode\u12"}') == r'{"text": "unicode\\u12"}'
    assert provider._sanitize_json(r'{"text": "unicode\u123"}') == r'{"text": "unicode\\u123"}'
    assert provider._sanitize_json(r'{"text": "unicode\u12345"}') == r'{"text": "unicode\u12345"}'  # \u1234 is valid, 5 is just next character

    # Invalid character escapes should have backslash escaped.
    # Note: \b is a valid JSON escape (backspace), so \beta is left as \beta.
    assert provider._sanitize_json(r'{"text": "math \alpha \beta"}') == r'{"text": "math \\alpha \beta"}'
    assert provider._sanitize_json(r'{"text": "invalid \x escape"}') == r'{"text": "invalid \\x escape"}'

    # Trailing backslash should be escaped
    assert provider._sanitize_json('hello \\') == 'hello \\\\'
