"""
Call a local Ollama instance to score a single requirement for:
  - ambiguity
  - completeness
  - verifiability
  - singularity
"""

import json
from typing import Any, Dict
import logging as lg

from click.core import F
import rich
import requests

from syntagmax.artifact import Artifact, ARef
from syntagmax.config import Config


class OllamaError(RuntimeError):
    pass


def ai_analyze(config: Config, artifacts: dict[ARef, Artifact]):
    for artifact in artifacts.values():
        lg.info(f'Launching AI analysis for {artifact.ref()}')

        if 'content' not in artifact.fields:
            lg.warning(f'No content for {artifact.ref()}')
            continue

        result = analyse_requirement(artifact.fields['content'])

        rich.print(f'[bold green]Metrics for {artifact.ref()}:[/bold green]')
        rich.print(f'Ambiguity: {result['metrics']['ambiguity']}')
        rich.print(f'Completeness: {result['metrics']['completeness']}')
        rich.print(f'Verifiability: {result['metrics']['verifiability']}')
        rich.print(f'Singularity: {result['metrics']['singularity']}')

        lg.debug(f'Metrics {artifact!r}, {result!r}')


def analyse_requirement(
    requirement_text: str,
    *,
    model: str = 'deepseek-v3.1:671b-cloud',
    host: str = 'http://localhost:11434',
    timeout_s: float = 60.0,
) -> Dict[str, Any]:
    """
    Analyse requirement quality using a local Ollama model.

    Returns a dict:
      {
        "metrics": {
          "ambiguity": float (0..1, higher is better),
          "completeness": float (0..1),
          "verifiability": float (0..1),
          "singularity": float (0..1)
        },
        "evidence": [ {
         "metric": str,
         "issue": str,
         "evidence": str,
         "fix_hint": str
         } ... ],
        "questions": [ str ... ],
        "rewrite": { "shall": str, "acceptance_criteria": [str ...] }
      }
    """

    if not requirement_text or not requirement_text.strip():
        raise ValueError('requirement_text must be a non-empty string')

    schema = {
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

    # Rubric: higher score = better quality. Keep concise; avoid prose in output.
    prompt = f"""
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

    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'Return only JSON; no prose; obey the schema exactly.'},
            {'role': 'user', 'content': prompt},
        ],
        # Structured outputs: JSON schema in format
        'format': schema,
        'stream': False,
    }

    url = f'{host.rstrip("/")}/api/chat'
    raw = _http_post_json(url, body, timeout_s=timeout_s)

    try:
        content = raw['message']['content']
    except Exception as e:
        raise OllamaError(f'Unexpected Ollama response shape: {raw!r}') from e

    try:
        content = content.lstrip('```json').rstrip('```')
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise OllamaError(f'Model did not return valid JSON. content={content!r}') from e

    _basic_validate(result)
    return result


def _http_post_json(
    url: str, payload: dict[str, Any], *, timeout_s: float
) -> dict[str, Any]:
    resp = None

    try:
        lg.debug(f'Calling Ollama at {url}')

        resp = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=timeout_s,
        )

        resp.raise_for_status()
        return resp.json()

    except Exception as e:
        lg.debug(f'Failed to call Ollama with {payload!r}')
        lg.debug(f'Response: {resp.text!r}' if resp else 'No response')
        raise OllamaError(f'Failed to call Ollama: {e}') from e


def _basic_validate(result: Dict[str, Any]) -> None:
    metrics = result.get('metrics')
    if not isinstance(metrics, dict):
        raise OllamaError("Missing/invalid 'metrics'")

    for k in ('ambiguity', 'completeness', 'verifiability', 'singularity'):
        v = metrics.get(k)  # type: ignore

        if not isinstance(v, (int, float)) or not (0.0 <= float(v) <= 1.0):
            raise OllamaError(f'metrics.{k} must be a number in [0,1], got {v!r}')

    evidence = result.get('evidence')
    if not isinstance(evidence, list):
        raise OllamaError("Missing/invalid 'evidence' (must be an array)")

    questions = result.get('questions')
    if not isinstance(questions, list):
        raise OllamaError("Missing/invalid 'questions' (must be an array)")

    rewrite = result.get('rewrite')
    if not isinstance(rewrite, dict) or 'shall' not in rewrite or 'acceptance_criteria' not in rewrite:
        raise OllamaError("Missing/invalid 'rewrite'")
