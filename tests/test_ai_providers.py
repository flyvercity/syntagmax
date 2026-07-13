# SPDX-License-Identifier: MIT
import pytest
from unittest.mock import MagicMock, patch, mock_open
import json

from syntagmax.config import AIConfig
from syntagmax.ai_providers import BedrockProvider, AIError

def test_bedrock_provider_requests_success():
    config = AIConfig(
        provider="bedrock",
        model="anthropic.claude-3-sonnet-20240229-v1:0",
        aws_region_name="us-east-1",
        aws_api_key="fake-api-key",
        timeout_s=10.0
    )
    provider = BedrockProvider(config)

    mock_response_body = {
        "content": [
            {
                "text": json.dumps({
                    "metrics": {
                        "ambiguity": 0.1,
                        "completeness": 0.9,
                        "verifiability": 0.8,
                        "singularity": 0.95
                    },
                    "evidence": [],
                    "questions": [],
                    "rewrite": {
                        "shall": "The system shall do X.",
                        "acceptance_criteria": ["Criteria 1"]
                    }
                })
            }
        ]
    }

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_body
        mock_post.return_value = mock_resp

        result = provider.analyze_requirement("The system should do X.")

        mock_post.assert_called_once()
        assert result["metrics"]["ambiguity"] == 0.1
        assert result["rewrite"]["shall"] == "The system shall do X."

def test_bedrock_provider_requests_failure():
    config = AIConfig(
        provider="bedrock",
        aws_region_name="us-east-1",
        aws_api_key="fake-api-key"
    )
    provider = BedrockProvider(config)

    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("HTTP Error")
        with pytest.raises(AIError, match="Failed to call Bedrock via requests"):
            provider.analyze_requirement("The system should do X.")

def test_bedrock_provider_boto3_success():
    config = AIConfig(
        provider="bedrock",
        aws_access_key_id="fake-access-key",
        aws_secret_access_key="fake-secret-key",
        aws_session_token="fake-session-token",
        aws_region_name="us-east-1"
    )
    provider = BedrockProvider(config)

    mock_response_body = {
        "content": [
            {
                "text": json.dumps({
                    "metrics": {
                        "ambiguity": 0.2,
                        "completeness": 0.8,
                        "verifiability": 0.7,
                        "singularity": 0.9
                    },
                    "evidence": [],
                    "questions": [],
                    "rewrite": {
                        "shall": "The system shall do Y.",
                        "acceptance_criteria": []
                    }
                })
            }
        ]
    }

    # Mock boto3 client
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps(mock_response_body).encode("utf-8")
    mock_client.invoke_model.return_value = {"body": mock_body}

    with patch("boto3.client", return_value=mock_client) as mock_boto:
        result = provider.analyze_requirement("The system should do Y.")

        mock_boto.assert_called_once_with(
            service_name="bedrock-runtime",
            region_name="us-east-1",
            aws_access_key_id="fake-access-key",
            aws_secret_access_key="fake-secret-key",
            aws_session_token="fake-session-token"
        )
        assert result["metrics"]["ambiguity"] == 0.2
