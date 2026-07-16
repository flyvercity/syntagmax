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


def test_redact_sensitive_info():
    config = MagicMock(spec=AIConfig)
    provider = OllamaProvider(config)

    # Test nested dict redaction
    payload = {
        'api-key': 'supersecretkey',
        'X-Goog-Api-Key': 'geminisecret',
        'nested': {'Authorization': 'Bearer 12345', 'normal_field': 'hello', 'list_field': [{'x-api-key': 'anthropicsecret', 'other': 'abc'}]},
    }
    redacted = provider._redact_sensitive_info(payload)
    assert redacted['api-key'] == '***REDACTED***'
    assert redacted['X-Goog-Api-Key'] == '***REDACTED***'
    assert redacted['nested']['Authorization'] == '***REDACTED***'
    assert redacted['nested']['normal_field'] == 'hello'
    assert redacted['nested']['list_field'][0]['x-api-key'] == '***REDACTED***'
    assert redacted['nested']['list_field'][0]['other'] == 'abc'

    # Test URL redaction
    url = 'https://some-api.com/v1?key=mysecretkey&other=val'
    assert provider._redact_sensitive_info(url) == 'https://some-api.com/v1?key=***REDACTED***&other=val'


def test_gemini_provider_logs_redacted(caplog):
    from syntagmax.ai_providers import GeminiProvider
    import logging

    config = AIConfig(
        provider='gemini',
        gemini_api_key='fake-gemini-key',
        model='gemini-1.5-pro',
    )
    provider = GeminiProvider(config)

    mock_response_body = {
        'candidates': [
            {
                'content': {
                    'parts': [
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
                                        'shall': 'The system shall do Z.',
                                        'acceptance_criteria': [],
                                    },
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_body
        mock_post.return_value = mock_resp

        with caplog.at_level(logging.DEBUG):
            result = provider.analyze_requirement('The system should do Z.')

        assert result['metrics']['ambiguity'] == 0.1
        # Check logs
        log_texts = [record.message for record in caplog.records]
        assert any('Calling Gemini at' in text for text in log_texts)
        assert any('Body:' in text for text in log_texts)
        # Ensure the actual secret key or unredacted keys never appear
        for log_text in log_texts:
            assert 'fake-gemini-key' not in log_text
