"""
Call AI provider to score a single requirement for:
  - ambiguity
  - completeness
  - verifiability
  - singularity
"""

import logging as lg

import rich

from syntagmax.artifact import Artifact, ARef
from syntagmax.config import Config
from syntagmax.ai_providers import (
    AIProvider,
    OllamaProvider,
    AnthropicProvider,
    OpenAIProvider,
    GeminiProvider,
    BedrockProvider,
)


def ai_analyze(config: Config, artifacts: dict[ARef, Artifact]):
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
        lg.error(f'Unknown AI provider: {provider_name}')
        return

    for artifact in artifacts.values():
        lg.info(f'Launching AI analysis for {artifact.ref()}')

        if 'content' not in artifact.fields:
            lg.warning(f'No content for {artifact.ref()}')
            continue

        try:
            result = provider.analyze_requirement(artifact.fields['content'])

            rich.print(f'[bold green]Metrics for {artifact.ref()}:[/bold green]')
            rich.print(f'Ambiguity: {result["metrics"]["ambiguity"]}')
            rich.print(f'Completeness: {result["metrics"]["completeness"]}')
            rich.print(f'Verifiability: {result["metrics"]["verifiability"]}')
            rich.print(f'Singularity: {result["metrics"]["singularity"]}')

            lg.debug(f'Metrics {artifact!r}, {result!r}')
        except Exception as e:
            lg.error(f'AI analysis failed for {artifact.ref()}: {e}')
