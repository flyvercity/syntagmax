# SPDX-License-Identifier: MIT

from abc import ABC, abstractmethod
from typing import Any, Dict
import logging as lg
import json
import os
import requests
import re

from syntagmax.config import AIConfig

class AIError(RuntimeError):
    pass

class AIProvider(ABC):
    def __init__(self, config: AIConfig):
        self.config = config

    @abstractmethod
    def analyze_requirement(self, requirement_text: str) -> Dict[str, Any]:
        pass

    def _get_schema(self) -> Dict[str, Any]:
        # Return the JSON schema used for all providers
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'metrics': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'ambiguity': {'type': 'number', 'minimum': 0, 'maximum': 1},
                        'completeness': {'type': 'number', 'minimum': 0, 'maximum': 1},
                        'verifiability': {'type': 'number', 'minimum': 0, 'maximum': 1},
                        'singularity': {'type': 'number', 'minimum': 0, 'maximum': 1},
                    },
                    'required': ['ambiguity', 'completeness', 'verifiability', 'singularity'],
                },
                'evidence': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'metric': {
                                'type': 'string',
                                'enum': ['ambiguity', 'completeness', 'verifiability', 'singularity'],
                            },
                            'issue': {'type': 'string'},
                            'evidence': {'type': 'string'},
                            'fix_hint': {'type': 'string'},
                        },
                        'required': ['metric', 'issue', 'evidence', 'fix_hint'],
                    },
                },
                'questions': {'type': 'array', 'items': {'type': 'string'}},
                'rewrite': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'shall': {'type': 'string'},
                        'acceptance_criteria': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': ['shall', 'acceptance_criteria'],
                },
            },
            'required': ['metrics', 'evidence', 'questions', 'rewrite'],
        }

    def _get_prompt(self, requirement_text: str) -> str:
        schema = self._get_schema()
        return f"""
Return ONLY JSON that conforms to the provided JSON schema.

You are analysing a single system requirement statement for quality.
Scores are 0..1 where 1 means excellent.

Definitions:
- ambiguity: clarity of terms and references; penalise vague adjectives/adverbs (e.g., "quickly"),
  weak modals ("should/may/could"), undefined actors/objects, and ambiguous pronouns.
- completeness: includes actor, action, object, conditions/triggers where relevant, and constraints/limits where implied.
- verifiability: can be tested/inspected objectively; penalise subjective qualities without operational definition.
- singularity: expresses a single obligation; penalise compound requirements ("and/or", multiple obligations).

Requirement text:
{requirement_text.strip()}

JSON schema (for grounding; still return JSON only):
{json.dumps(schema, ensure_ascii=False)}
""".strip()

    def _basic_validate(self, result: Dict[str, Any]) -> None:
        metrics = result.get('metrics')
        if not isinstance(metrics, dict):
            raise AIError("Missing/invalid 'metrics'")

        for k in ('ambiguity', 'completeness', 'verifiability', 'singularity'):
            v = metrics.get(k)  # type: ignore

            if not isinstance(v, (int, float)) or not (0.0 <= float(v) <= 1.0):
                raise AIError(f'metrics.{k} must be a number in [0,1], got {v!r}')

        evidence = result.get('evidence')
        if not isinstance(evidence, list):
            raise AIError("Missing/invalid 'evidence' (must be an array)")

        questions = result.get('questions')
        if not isinstance(questions, list):
            raise AIError("Missing/invalid 'questions' (must be an array)")

        rewrite = result.get('rewrite')
        if not isinstance(rewrite, dict) or 'shall' not in rewrite or 'acceptance_criteria' not in rewrite:
            raise AIError("Missing/invalid 'rewrite'")


class OllamaProvider(AIProvider):
    def analyze_requirement(self, requirement_text: str) -> Dict[str, Any]:
        if not requirement_text or not requirement_text.strip():
            raise ValueError('requirement_text must be a non-empty string')

        model = self.config.model or 'deepseek-v3.1:671b-cloud'
        host = self.config.ollama_host
        timeout_s = self.config.timeout_s
        schema = self._get_schema()
        prompt = self._get_prompt(requirement_text)

        body = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'Return only JSON; no prose; obey the schema exactly.'},
                {'role': 'user', 'content': prompt},
            ],
            'format': schema,
            'stream': False,
        }

        url = f'{host.rstrip("/")}/api/chat'

        resp = None
        try:
            lg.debug(f'Calling Ollama at {url}')
            resp = requests.post(
                url,
                json=body,
                headers={'Content-Type': 'application/json'},
                timeout=timeout_s,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            lg.debug(f'Failed to call Ollama with {body!r}')
            if resp:
                lg.debug(f'Response: {resp.text!r}')
            raise AIError(f'Failed to call Ollama: {e}') from e

        try:
            content = raw['message']['content']
        except Exception as e:
            raise AIError(f'Unexpected Ollama response shape: {raw!r}') from e

        try:
            content = content.lstrip('```json').rstrip('```')
            result = json.loads(content)
        except json.JSONDecodeError as e:
            raise AIError(f'Model did not return valid JSON. content={content!r}') from e

        self._basic_validate(result)
        return result


class AnthropicProvider(AIProvider):
    def analyze_requirement(self, requirement_text: str) -> Dict[str, Any]:
        if not requirement_text or not requirement_text.strip():
            raise ValueError('requirement_text must be a non-empty string')

        api_key = self.config.anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
             raise AIError("Anthropic API Key is required (set via config or ANTHROPIC_API_KEY env var)")

        model = self.config.model or 'claude-3-5-sonnet-20240620'
        timeout_s = self.config.timeout_s
        prompt = self._get_prompt(requirement_text)

        body = {
            'model': model,
            'max_tokens': 4096,
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }

        url = 'https://api.anthropic.com/v1/messages'
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        resp = None
        try:
            lg.debug(f'Calling Anthropic at {url}')
            lg.debug(f'Headers: {headers}')
            lg.debug(f'Body: {json.dumps(body)}')
            resp = requests.post(
                url,
                json=body,
                headers=headers,
                timeout=timeout_s,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            lg.debug(f'Failed to call Anthropic with {body!r}')
            if resp:
                 lg.debug(f'Response: {resp.text!r}')
            raise AIError(f'Failed to call Anthropic: {e}') from e

        try:
            content = raw['content'][0]['text']
            # Sometimes Claude wraps json in markdown block
            content = content.strip().lstrip('```json').rstrip('```')
            # Fix for potential trailing ```
            if content.endswith('```'):
                content = content[:-3]

            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                content = match.group(0)

            result = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
             raise AIError(f'Unexpected Anthropic response: {raw!r}') from e

        self._basic_validate(result)
        return result


class OpenAIProvider(AIProvider):
    def analyze_requirement(self, requirement_text: str) -> Dict[str, Any]:
        if not requirement_text or not requirement_text.strip():
            raise ValueError('requirement_text must be a non-empty string')

        api_key = self.config.openai_api_key or os.environ.get('OPENAI_API_KEY')
        if not api_key:
             raise AIError("OpenAI API Key is required (set via config or OPENAI_API_KEY env var)")

        model = self.config.model or 'gpt-4o'
        timeout_s = self.config.timeout_s
        prompt = self._get_prompt(requirement_text)

        body = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'You are a helpful assistant that outputs JSON.'},
                {'role': 'user', 'content': prompt}
            ],
            'response_format': {'type': 'json_object'}
        }

        url = 'https://api.openai.com/v1/chat/completions'
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        resp = None
        try:
            lg.debug(f'Calling OpenAI at {url}')
            resp = requests.post(
                url,
                json=body,
                headers=headers,
                timeout=timeout_s,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            lg.debug(f'Failed to call OpenAI with {body!r}')
            if resp:
                 lg.debug(f'Response: {resp.text!r}')
            raise AIError(f'Failed to call OpenAI: {e}') from e

        try:
            content = raw['choices'][0]['message']['content']
            result = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
             raise AIError(f'Unexpected OpenAI response: {raw!r}') from e

        self._basic_validate(result)
        return result


class GeminiProvider(AIProvider):
    def analyze_requirement(self, requirement_text: str) -> Dict[str, Any]:
        if not requirement_text or not requirement_text.strip():
             raise ValueError('requirement_text must be a non-empty string')

        api_key = self.config.gemini_api_key or os.environ.get('GEMINI_API_KEY')
        if not api_key:
             raise AIError("Gemini API Key is required (set via config or GEMINI_API_KEY env var)")

        model = self.config.model or 'gemini-1.5-pro'
        timeout_s = self.config.timeout_s
        prompt = self._get_prompt(requirement_text)

        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'

        body = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        resp = None
        try:
            lg.debug(f'Calling Gemini at {url}')
            lg.debug(f'Body: {json.dumps(body)}')
            resp = requests.post(
                url,
                json=body,
                headers={'Content-Type': 'application/json'},
                timeout=timeout_s,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            lg.debug(f'Failed to call Gemini with {body!r}')
            if resp:
                 lg.debug(f'Response: {resp.text!r}')
            raise AIError(f'Failed to call Gemini: {e}') from e

        try:
            content = raw['candidates'][0]['content']['parts'][0]['text']
            
            # Sometimes Gemini wraps json in markdown block or returns some prose
            content = content.strip().lstrip('```json').rstrip('```')
            if content.endswith('```'):
                content = content[:-3]

            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                content = match.group(0)
            
            # Sanitization: Gemini often returns single backslashes in mathematical notation
            # which are invalid in JSON strings unless escaped.
            # We escape backslashes that are not followed by a valid escape character.
            # Valid escapes in JSON: ", \, /, b, f, n, r, t, uXXXX
            def escape_invalid_slashes(m):
                s = m.group(0)
                if len(s) > 1 and s[1] in '"\\/bfnrtu':
                    return s
                return '\\\\' + s[1:] if len(s) > 1 else '\\\\'

            content = re.sub(r'\\.', escape_invalid_slashes, content)

            result = json.loads(content)
        except (KeyError, IndexError) as e:
             raise AIError(f'Unexpected Gemini response shape: {raw!r}') from e
        except json.JSONDecodeError as e:
             raise AIError(f'Model did not return valid JSON. content={content!r}') from e

        self._basic_validate(result)
        return result


class BedrockProvider(AIProvider):
    def analyze_requirement(self, requirement_text: str) -> Dict[str, Any]:
        try:
            import boto3
        except ImportError:
            raise AIError("boto3 is required for AWS Bedrock support. Please install it.")

        if not requirement_text or not requirement_text.strip():
            raise ValueError('requirement_text must be a non-empty string')

        model = self.config.model or 'anthropic.claude-3-sonnet-20240229-v1:0'
        region = self.config.aws_region_name

        if 'anthropic' not in model and 'claude' not in model:
             lg.warning(f"Bedrock model '{model}' might not be supported. Only Anthropic Claude models are verified to work with the current prompt/body format.")

        prompt = self._get_prompt(requirement_text)

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        })

        try:
            kwargs = {'service_name': 'bedrock-runtime'}
            if region:
                kwargs['region_name'] = region

            if self.config.aws_access_key_id and self.config.aws_secret_access_key:
                kwargs['aws_access_key_id'] = self.config.aws_access_key_id
                kwargs['aws_secret_access_key'] = self.config.aws_secret_access_key

            client = boto3.client(**kwargs)

            lg.debug(f'Calling Bedrock model {model}')
            response = client.invoke_model(
                body=body,
                modelId=model,
                accept='application/json',
                contentType='application/json'
            )

            response_body = json.loads(response.get('body').read())
            content = response_body.get('content')[0].get('text')

            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                content = match.group(0)

            result = json.loads(content)

        except Exception as e:
             raise AIError(f'Failed to call Bedrock: {e}') from e

        self._basic_validate(result)
        return result
