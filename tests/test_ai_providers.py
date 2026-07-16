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

    # Test basic dictionary redaction
    data = {
        'api_key': 'supersecretkey123',
        'Authorization': 'Bearer mytoken',
        'normal_field': 'not_sensitive',
        'nested': {'x-api-key': 'anothersecret', 'deeply': [{'apikey': 'nested_secret'}, {'other': 'clean'}]},
    }
    redacted = provider._redact_sensitive_info(data)
    assert redacted['api_key'] == '***REDACTED***'
    assert redacted['Authorization'] == '***REDACTED***'
    assert redacted['normal_field'] == 'not_sensitive'
    assert redacted['nested']['x-api-key'] == '***REDACTED***'
    assert redacted['nested']['deeply'][0]['apikey'] == '***REDACTED***'
    assert redacted['nested']['deeply'][1]['other'] == 'clean'

    # Test circular reference handling
    circular_dict = {'normal': 'value'}
    circular_dict['loop'] = circular_dict
    redacted_circular = provider._redact_sensitive_info(circular_dict)
    assert redacted_circular['normal'] == 'value'
    assert redacted_circular['loop'] is redacted_circular

    # Test URL redaction
    url = 'https://api.openai.com/v1/chat/completions?api-key=supersecret&other=val'
    redacted_url = provider._redact_sensitive_info(url)
    assert 'supersecret' not in redacted_url
    assert '***REDACTED***' in redacted_url

    url2 = 'https://example.com/?key=mykey'
    redacted_url2 = provider._redact_sensitive_info(url2)
    assert 'mykey' not in redacted_url2
    assert '***REDACTED***' in redacted_url2


def test_provider_logging_redacts_body(caplog):
    import logging

    config = AIConfig(
        provider='anthropic',
        anthropic_api_key='anthropic-secret-api-key',
        model='claude-3-5-sonnet',
    )
    from syntagmax.ai_providers import AnthropicProvider

    provider = AnthropicProvider(config)

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

    with caplog.at_level(logging.DEBUG):
        with patch('requests.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response_body
            mock_post.return_value = mock_resp

            provider.analyze_requirement('The system should do X.')

            # Verify that logging redacted the sensitive keys
            log_messages = [record.message for record in caplog.records]
            # Ensure "anthropic-secret-api-key" was NOT logged
            for msg in log_messages:
                assert 'anthropic-secret-api-key' not in msg
                if 'Headers' in msg:
                    assert '***REDACTED***' in msg
