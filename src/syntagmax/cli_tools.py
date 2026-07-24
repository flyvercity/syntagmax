# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: Syntagmax CLI - Trace, MCP, Schema, and CI commands.

import sys
from pathlib import Path

import click

import syntagmax.utils as u
from syntagmax.config import Config, Params


@click.command(help='Export traceability matrix as CSV/TSV')
@click.pass_obj
@click.option('--child', required=True, help='Artifact type of the child (e.g., REQ)')
@click.option('--parent', required=True, help='Artifact type of the parent (e.g., SYS)')
@click.option('--forward/--reverse', default=True, help='Direction: forward (child→parent) or reverse (parent→child)')
@click.option('--attribute', multiple=True, help='Additional lead artifact attributes to include as columns')
@click.option('--flat', is_flag=True, help='Combine multiple linked IDs into semicolon-separated values')
@click.option('--delimiter', default=None, help='Column delimiter (default: "," or "\\t" for .tsv files)')
@click.option('--output', default='.syntagmax/reports/trace.csv', help='Output file path (use "console" for stdout)')
@click.option('-f', '--config-file', type=click.Path(), default='.syntagmax/config.toml')
def trace(
    obj: Params,
    child: str,
    parent: str,
    forward: bool,
    attribute: tuple[str, ...],
    flat: bool,
    delimiter: str | None,
    output: str,
    config_file: Path,
):
    from syntagmax.extract import extract, build_artifact_map
    from syntagmax.tree import populate_pids, build_tree
    from syntagmax.trace import build_trace_matrix, render_trace_csv
    from syntagmax.plugin import find_plugin_by_name, run_trace_export

    cfg_path = Path(config_file)
    if not cfg_path.exists():
        u.pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)

    config = Config(obj, cfg_path)
    errors: list[str] = []

    # Run pipeline manually to retain access to ArtifactMap
    artifacts_list = extract(config, errors)
    artifacts = build_artifact_map(artifacts_list, errors)
    populate_pids(config, artifacts, errors)
    build_tree(config, artifacts, errors)

    if errors:
        for err in errors:
            u.pprint(f'[yellow]Warning: {err}[/yellow]')

    # Validate child and parent types against metamodel if available
    if config.metamodel and 'artifacts' in config.metamodel:
        valid_types = config.metamodel['artifacts'].keys()
        if child not in valid_types:
            u.pprint(f'[yellow]Warning: Child artifact type "{child}" is not defined in the metamodel.[/yellow]')
        if parent not in valid_types:
            u.pprint(f'[yellow]Warning: Parent artifact type "{parent}" is not defined in the metamodel.[/yellow]')

    # Determine direction
    direction = 'forward' if forward else 'reverse'

    # Build the trace matrix
    matrix = build_trace_matrix(
        artifacts=artifacts,
        child_type=child,
        parent_type=parent,
        direction=direction,
        attributes=list(attribute),
        flat=flat,
    )

    if config.trace_plugins:
        # Delegate to configured plugins (run all sequentially)
        for plugin_name in config.trace_plugins:
            plugin = find_plugin_by_name(config.plugins(), plugin_name)
            run_trace_export(plugin, matrix, config)
            u.pprint(f'[green]Trace export completed via plugin "{plugin_name}"[/green]')
    else:
        # Determine delimiter
        if delimiter is not None:
            sep = delimiter.replace('\\t', '\t')
        elif output.endswith('.tsv'):
            sep = '\t'
        else:
            sep = ','

        csv_output = render_trace_csv(matrix, delimiter=sep)

        if output == 'console':
            print(csv_output, end='')
        else:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(csv_output, encoding='utf-8')
            u.pprint(f'[green]Trace matrix written to {output_path} ({len(matrix.records)} records)[/green]')


@click.group(help='MCP Server Management')
def mcp():
    pass


@mcp.command(help='Run the MCP server')
@click.pass_obj
@click.argument('config_path', type=click.Path(exists=True))
@click.option('--host', default='127.0.0.1', help='Host for SSE')
@click.option('--port', default=8000, help='Port for SSE')
@click.option('--sse-path', default='/', help='Path for SSE stream')
@click.option('--transport', default='stdio', type=click.Choice(['stdio', 'sse']), help='MCP transport to use')
def run(obj: Params, config_path: str, host: str, port: int, sse_path: str, transport: str):
    from syntagmax.mcp.server import run_mcp_server

    configurator = Config(obj, Path(config_path))
    run_mcp_server(configurator, host, port, sse_path, transport)


@click.group(help='Schema Management Commands')
def schema():
    pass


@schema.command(name='publish', help='Generate JSON Schema for the publishing configuration')
def schema_publish():
    import json
    from syntagmax.publish_config import PublishConfig

    schema_dict = PublishConfig.model_json_schema()
    print(json.dumps(schema_dict, indent=2))


@schema.command(name='config', help='Generate JSON Schema for the main project configuration (config.toml)')
def schema_config():
    import json
    from syntagmax.config import ConfigFile

    schema_dict = ConfigFile.model_json_schema()
    print(json.dumps(schema_dict, indent=2))


@click.group(help='Configure CI/CD pipelines')
@click.option('--target', type=click.Choice(['github', 'gitlab']), default='github', help='CI/CD target platform')
@click.pass_context
def ci(ctx: click.Context, target: str):
    ctx.ensure_object(dict)
    ctx.obj['ci_target'] = target


@ci.group(help='Install CI configuration files')
@click.pass_context
def install(ctx: click.Context):
    pass


@install.command(name='analyze', help='Install CI workflow for the analyze command')
@click.pass_obj
def ci_install_analyze(obj: Params):
    target = obj.get('ci_target', 'github')  # type: ignore

    if target == 'github':
        content = """name: Syntagmax Analyze

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  analyze:
    name: Syntagmax Analyze
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v8.3.2
        with:
          enable-cache: true

      - name: Install Syntagmax
        run: |
          uv tool install syntagmax

      - name: Run Analyze
        run: |
          syntagmax analyze

      - name: Upload Report Artifact
        uses: actions/upload-artifact@v7
        with:
          name: syntagmax-report
          path: .syntagmax/reports/report.md
"""
        workflow_dir = Path('.github/workflows')
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_file = workflow_dir / 'syntagmax-analyze.yml'
        workflow_file.write_text(content, encoding='utf-8')
        u.pprint(f'[green]GitHub workflow created at {workflow_file}[/green]')

    elif target == 'gitlab':
        content = """stages:
  - analyze

syntagmax-analyze:
  stage: analyze
  image: python:3.13-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
  before_script:
    - apt-get update && apt-get install -y curl
    - curl -LsSf https://astral.sh/uv/install.sh | sh
    - export PATH="$HOME/.local/bin:$PATH"
    - uv tool install syntagmax
  script:
    - syntagmax analyze
  artifacts:
    paths:
      - .syntagmax/reports/report.md
"""
        workflow_file = Path('.gitlab-ci.yml')
        workflow_file.write_text(content, encoding='utf-8')
        u.pprint(f'[green]GitLab CI configuration created at {workflow_file}[/green]')


@install.command(name='publish', help='Install CI workflow for the publish command')
@click.pass_obj
def ci_install_publish(obj: Params):
    target = obj.get('ci_target', 'github')  # type: ignore

    if target == 'github':
        content = """name: Syntagmax Publish

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  publish:
    name: Syntagmax Publish
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v8.3.2
        with:
          enable-cache: true

      - name: Install Syntagmax
        run: |
          uv tool install syntagmax

      - name: Run Publish
        run: |
          syntagmax publish --all --single

      - name: Upload Publish Artifact
        uses: actions/upload-artifact@v7
        with:
          name: syntagmax-publish
          path: .syntagmax/reports/published.md
"""
        workflow_dir = Path('.github/workflows')
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_file = workflow_dir / 'syntagmax-publish.yml'
        workflow_file.write_text(content, encoding='utf-8')
        u.pprint(f'[green]GitHub workflow created at {workflow_file}[/green]')

    elif target == 'gitlab':
        content = """stages:
  - publish

syntagmax-publish:
  stage: publish
  image: python:3.13-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
  before_script:
    - apt-get update && apt-get install -y curl git
    - curl -LsSf https://astral.sh/uv/install.sh | sh
    - export PATH="$HOME/.local/bin:$PATH"
    - uv tool install syntagmax
  script:
    - syntagmax publish --all --single
  artifacts:
    paths:
      - .syntagmax/reports/published.md
"""
        workflow_file = Path('.gitlab-ci.yml')
        workflow_file.write_text(content, encoding='utf-8')
        u.pprint(f'[green]GitLab CI configuration created at {workflow_file}[/green]')
