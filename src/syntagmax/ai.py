# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-01-06
# Description: Syntagmax Requirement Management System (RMS) AI Analysis Subsystem.

"""
Call AI provider to score a single requirement for:
  - ambiguity
  - completeness
  - verifiability
  - singularity
"""

import logging as lg

from syntagmax.artifact import ArtifactMap
from syntagmax.config import Config
from syntagmax.ai_providers import (
    AIProvider,
    OllamaProvider,
    AnthropicProvider,
    OpenAIProvider,
    GeminiProvider,
    BedrockProvider,
)


def ai_analyze(config: Config, artifacts: ArtifactMap, errors: list[str]) -> list[dict]:
    provider_name = config.ai.provider.lower()
    lg.info(f'Using AI provider: {provider_name}')

    provider: AIProvider
    if provider_name == 'ollama':
        provider = OllamaProvider(config.ai)
    elif provider_name == 'anthropic':
        provider = AnthropicProvider(config.ai)
    elif provider_name == 'openai':
        provider = OpenAIProvider(config.ai)
    elif provider_name == 'gemini':
        provider = GeminiProvider(config.ai)
    elif provider_name == 'bedrock':
        provider = BedrockProvider(config.ai)
    else:
        errors.append(f'Unknown AI provider: {provider_name}')
        return []

    results = []

    for artifact in artifacts.values():
        if artifact.atype == 'ROOT':
            continue

        lg.info(f'Launching AI analysis for {artifact.aid}')

        try:
            result = provider.analyze_requirement(artifact.contents())
            results.append({
                'aid': artifact.aid,
                'atype': artifact.atype,
                'ambiguity': result['metrics']['ambiguity'],
                'completeness': result['metrics']['completeness'],
                'verifiability': result['metrics']['verifiability'],
                'singularity': result['metrics']['singularity'],
            })
        except Exception as e:
            errors.append(f'AI analysis failed for {artifact}: {e}')

    return results
