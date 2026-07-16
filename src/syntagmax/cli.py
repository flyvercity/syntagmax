# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Syntagmax Requirement Management System (RMS) CLI Tool.

import logging as lg
import sys
import os
import traceback
from pathlib import Path
from typing import Any
from importlib.metadata import version

import click
from rich.logging import RichHandler

import syntagmax.utils as u
from syntagmax.config import Config, Params
from syntagmax.errors import RMSException, FatalError
from syntagmax.main import process, public_steps
from syntagmax.mcp.server import run_mcp_server
from syntagmax.init_cmd import init_project
from syntagmax.edit import renumber_artifacts
from syntagmax.edit_attrs import manipulate_attributes, load_csv_mapping
from syntagmax.edit_markers import renumber_markers


@click.group(help='RMS Entry Point')
@click.version_option(version('syntagmax'))
@click.pass_context
@click.option('--verbose', is_flag=True, help='Verbose output')
@click.option('--render-tree', is_flag=True, help='Render the artifact tree')
@click.option('--cwd', type=click.Path(exists=True), help='Change the working directory')
@click.option('--no-git', is_flag=True, help='Skip git history extraction')
@click.option('--output', default='.syntagmax/reports/report.md', help='Report output file (default: .syntagmax/reports/report.md)')
def rms(ctx: click.Context, **kwargs: dict[str, Any]):
    verbose = kwargs['verbose']
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO, handlers=[RichHandler()])
    ctx.obj = Params(**kwargs)  # type: ignore

    if ctx.obj['cwd']:
        lg.info(f'Changing working directory to: {ctx.obj["cwd"]}')
        os.chdir(ctx.obj['cwd'])

    lg.info(f'Verbose: {verbose}')


@rms.command(help='Initialize a new Syntagmax project')
@click.pass_context
def init(ctx: click.Context):
    cwd = ctx.obj.get('cwd') if ctx.obj else None
    init_project(cwd)
    u.pprint('[green]Initialized a new Syntagmax project.[/green]')


@rms.command(help='Run full analysis of the project')
@click.pass_obj
@click.option(
    '-f',
    '--config-file',
    type=click.Path(),
    default='.syntagmax/config.toml',
)
@click.option('--allow-dirty-worktree', is_flag=True, help='Allow analysis on a dirty git worktree')
@click.option('--suppress-tracing', is_flag=True, help='Suppress tracing model errors')
@click.argument('step', type=click.Choice(public_steps()), default='metrics')
def analyze(obj: Params, config_file: Path, allow_dirty_worktree: bool, suppress_tracing: bool, step: str):
    import sys

    cfg_path = Path(config_file)
    if not cfg_path.exists():
        u.pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)
    obj['allow_dirty_worktree'] = allow_dirty_worktree
    obj['suppress_tracing'] = suppress_tracing
    config = Config(obj, cfg_path)
    report = process(step, config)

    output = obj['output']
    markdown = report.render()

    if output == 'console':
        print(markdown)
    else:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding='utf-8')

    error_count = len(report.errors)
    if output != 'console':
        summary = f'Report written to {output}'
        if error_count:
            summary += f', {error_count} error(s) found'
        color = 'yellow' if error_count else 'green'
        u.pprint(f'[{color}]{summary}[/{color}]')


def _run_pandoc_conversion(md_path: Path, docx: bool, pdf: bool, reference_doc: Path | None = None):
    """Run Pandoc conversion for the given Markdown file."""
    from syntagmax.pandoc import convert

    formats = []
    if docx:
        formats.append(('docx', md_path.with_suffix('.docx')))
    if pdf:
        formats.append(('pdf', md_path.with_suffix('.pdf')))

    for fmt, out_path in formats:
        success, message = convert(md_path, out_path, fmt, reference_doc=reference_doc if fmt == 'docx' else None,
                                   resource_path=md_path.parent)
        if success:
            u.pprint(f'[green]Converted to {fmt.upper()}: {out_path}[/green]')
        else:
            u.pprint(f'[yellow]Pandoc conversion to {fmt.upper()} failed: {message}[/yellow]')


def _copy_manifest_images(manifest, output_dir: Path):
    """Copy images from the manifest to output_dir/images/, with stale cleanup."""
    import shutil

    if not manifest:
        return

    images_dir = output_dir / 'images'

    # Clean stale images
    if images_dir.exists():
        for f in images_dir.iterdir():
            if f.is_file():
                f.unlink()
    else:
        images_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for source, target_rel in manifest.entries.items():
        dest = output_dir / target_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(source, dest)
            copied += 1
        else:
            lg.warning(f'Image source file not found, skipping: {source}')

    if copied:
        u.pprint(f'[green]Copied {copied} image(s) to {images_dir}[/green]')


@rms.command(help='Publish project to markdown document(s)')
@click.pass_obj
@click.argument('records', nargs=-1)
@click.option('--all', 'publish_all', is_flag=True, help='Publish all input records')
@click.option('--single', is_flag=True, help='Compile all published records sequentially into a single file')
@click.option('--output', 'output_path', type=click.Path(), default=None, help='Output directory or file path')
@click.option('-f', '--config-file', type=click.Path(), default='.syntagmax/config.toml')
@click.option('--date-suffix', is_flag=True, help='Append date suffix to filenames (only valid when publishing separate files)')
@click.option('--docx', is_flag=True, help='Convert output to DOCX via Pandoc')
@click.option('--pdf', is_flag=True, help='Convert output to PDF via Pandoc')
@click.option('--docx-template', 'docx_template_path', default=None, help='Override DOCX reference template path (use "none" to disable)')
@click.option('--pre-filter', 'pre_filter_name', default=None, help='Run a pre-publishing block filter plugin')
def publish(
    obj: Params, records: tuple[str, ...], publish_all: bool, single: bool,
    output_path: str | None, config_file: Path, date_suffix: bool, docx: bool, pdf: bool,
    docx_template_path: str | None, pre_filter_name: str | None,
):
    from datetime import datetime
    from syntagmax.publish import build_block_tree, render_block_tree
    from syntagmax.blocks import ArtifactBlock, TextBlock
    from syntagmax.plugin import run_block_transforms, run_markdown_transforms, find_plugin_by_name, run_pre_filter
    import sys

    if not records and not publish_all:
        u.pprint('[red]Error: Either RECORD names or --all must be specified.[/red]')
        sys.exit(1)

    if single and date_suffix:
        u.pprint('[red]Error: --date-suffix cannot be combined with --single.[/red]')
        sys.exit(1)

    cfg_path = Path(config_file)
    if not cfg_path.exists():
        u.pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)

    config = Config(obj, cfg_path)

    available_records = {r.name: r for r in config.input_records()}
    selected_records = []

    if publish_all:
        selected_records = list(config.input_records())
    else:
        for r_name in records:
            if r_name not in available_records:
                u.pprint(f'[red]Error: Input record "{r_name}" not found in config.[/red]')
                sys.exit(1)
            selected_records.append(available_records[r_name])

    if output_path is None:
        if single:
            output_path = '.syntagmax/reports/published.md'
        else:
            output_path = '.syntagmax/reports/'

    # Check Pandoc availability once if conversion is requested
    pandoc_available = False
    if docx or pdf:
        from syntagmax.pandoc import check_pandoc
        pandoc_available = check_pandoc()
        if not pandoc_available:
            lg.warning('pandoc executable not found in PATH')
            u.pprint('[yellow]Warning: pandoc not found in PATH. DOCX/PDF conversion will be skipped.[/yellow]')

    # Resolve DOCX template
    def _resolve_template_for_record(record):
        """Resolve the DOCX template for a given record."""
        if docx_template_path is not None:
            # CLI override takes precedence
            if docx_template_path.lower() == 'none':
                return None
            cli_template = Path(docx_template_path)
            if not cli_template.exists():
                from syntagmax.errors import FatalError
                raise FatalError([f'DOCX template not found: {cli_template} (--docx-template)'])
            return cli_template
        from syntagmax.pandoc import resolve_docx_template
        pub_config = config.load_publish_config(record)
        return resolve_docx_template(pub_config, record.name, cfg_path.parent)

    out_p = Path(output_path)

    if single:
        tree, block_errors = build_block_tree(config)
        for err in block_errors:
            u.pprint(f'[red]Error: {err}[/red]')
        selected_names = {r.name for r in selected_records}
        tree.inputs = [inp for inp in tree.inputs if inp.name in selected_names]

        # Run plugin block transforms
        tree = run_block_transforms(config.plugins(), tree, config)

        # Run pre-publishing block filter if specified
        if pre_filter_name:
            pre_filter_plugin = find_plugin_by_name(config.plugins(), pre_filter_name)
            tree = run_pre_filter(pre_filter_plugin, tree, config)

        markdown, manifest = render_block_tree(tree, config, multi_record=(len(selected_records) > 1))

        # Run plugin markdown transforms
        markdown = run_markdown_transforms(config.plugins(), markdown, config)

        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(markdown, encoding='utf-8')

        # Copy images
        _copy_manifest_images(manifest, out_p.parent)

        num_artifacts = 0
        num_text_blocks = 0
        for inp in tree.inputs:
            for f in inp.files:
                for b in f.blocks:
                    if isinstance(b, ArtifactBlock):
                        num_artifacts += 1
                    elif isinstance(b, TextBlock):
                        num_text_blocks += 1

        u.pprint(f'[green]Published consolidated report to {out_p} ({num_artifacts} artifacts, {num_text_blocks} text blocks)[/green]')

        if pandoc_available:
            reference_doc = None
            if docx:
                # Resolve template using first record, warn on conflicts
                reference_doc = _resolve_template_for_record(selected_records[0])
                if len(selected_records) > 1 and docx_template_path is None:
                    for rec in selected_records[1:]:
                        other_template = _resolve_template_for_record(rec)
                        if other_template != reference_doc:
                            tpl_name = str(reference_doc) if reference_doc else 'none'
                            u.pprint(f'[yellow]Warning: Conflicting DOCX templates across records in --single mode. Using: {tpl_name}[/yellow]')
                            break
            _run_pandoc_conversion(out_p, docx, pdf, reference_doc=reference_doc)
    else:
        out_p.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime('%Y-%m-%d')

        from syntagmax.publish_context import ImageManifest
        combined_manifest = ImageManifest()
        published_files: list[tuple[Path, object]] = []  # (file_path, record) for deferred Pandoc

        for record in selected_records:
            tree, block_errors = build_block_tree(config)
            for err in block_errors:
                u.pprint(f'[red]Error: {err}[/red]')
            tree.inputs = [inp for inp in tree.inputs if inp.name == record.name]

            # Run plugin block transforms
            tree = run_block_transforms(config.plugins(), tree, config)

            # Run pre-publishing block filter if specified
            if pre_filter_name:
                pre_filter_plugin = find_plugin_by_name(config.plugins(), pre_filter_name)
                tree = run_pre_filter(pre_filter_plugin, tree, config)

            markdown, manifest = render_block_tree(tree, config, multi_record=False)

            # Run plugin markdown transforms
            markdown = run_markdown_transforms(config.plugins(), markdown, config)

            combined_manifest.merge(manifest)

            safe_record_name = Path(record.name).name.replace('/', '_').replace('\\', '_')

            if safe_record_name in ('.', '..') or not safe_record_name:

                u.pprint(f'[red]Error: Invalid record name for output filename: "{record.name}".[/red]')

                sys.exit(1)



            if date_suffix:
                filename = f'{safe_record_name}_{date_str}.md'

            else:
                filename = f'{safe_record_name}.md'


            file_path = out_p / filename
            file_path.write_text(markdown, encoding='utf-8')

            num_artifacts = 0
            num_text_blocks = 0
            for inp in tree.inputs:
                for f in inp.files:
                    for b in f.blocks:
                        if isinstance(b, ArtifactBlock):
                            num_artifacts += 1
                        elif isinstance(b, TextBlock):
                            num_text_blocks += 1

            u.pprint(f'[green]Published {record.name} to {file_path} ({num_artifacts} artifacts, {num_text_blocks} text blocks)[/green]')

            published_files.append((file_path, record))

        # Copy images before Pandoc conversion so images/ is available on disc
        _copy_manifest_images(combined_manifest, out_p)

        # Pandoc conversion (images now present)
        if pandoc_available:
            for file_path, record in published_files:
                reference_doc = _resolve_template_for_record(record) if docx else None
                _run_pandoc_conversion(file_path, docx, pdf, reference_doc=reference_doc)


@rms.command(help='Export traceability matrix as CSV/TSV')
@click.pass_obj
@click.option('--child', required=True, help='Artifact type of the child (e.g., REQ)')
@click.option('--parent', required=True, help='Artifact type of the parent (e.g., SYS)')
@click.option('--forward/--reverse', default=True, help='Direction: forward (child→parent) or reverse (parent→child)')
@click.option('--attribute', multiple=True, help='Additional lead artifact attributes to include as columns')
@click.option('--flat', is_flag=True, help='Combine multiple linked IDs into semicolon-separated values')
@click.option('--delimiter', default=None, help='Column delimiter (default: "," or "\\t" for .tsv files)')
@click.option('--plugin', 'plugin_name', default=None, help='Use a named plugin for export instead of CSV')
@click.option('--output', default='.syntagmax/reports/trace.csv', help='Output file path (use "console" for stdout)')
@click.option('-f', '--config-file', type=click.Path(), default='.syntagmax/config.toml')
def trace(
    obj: Params, child: str, parent: str, forward: bool, attribute: tuple[str, ...],
    flat: bool, delimiter: str | None, plugin_name: str | None, output: str, config_file: Path,
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

    if plugin_name:
        # Delegate to plugin
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


def _get_working_tree_changed_files(repo, compare_hash: str):
    """Get changed files between a commit and the working tree.

    Uses git diff --name-status to compare a given revision against the
    current working directory state.
    """
    from syntagmax.change_diff import FileDiff, FileStatus

    raw = repo.git.diff('--name-status', compare_hash)
    results = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        status_code = parts[0][0]  # First character: A, D, M, R
        if status_code == 'A':
            results.append(FileDiff(path=parts[1], status=FileStatus.ADDED))
        elif status_code == 'D':
            results.append(FileDiff(path=parts[1], status=FileStatus.REMOVED))
        elif status_code == 'M':
            results.append(FileDiff(path=parts[1], status=FileStatus.MODIFIED))
        elif status_code == 'R':
            results.append(FileDiff(path=parts[2] if len(parts) > 2 else parts[1], status=FileStatus.RENAMED, old_path=parts[1]))
    return results


def _read_file_safe(base_path: Path, rel_path: str) -> str | None:
    """Read a file safely, returning None if not found."""
    try:
        file_path = base_path / rel_path
        if file_path.is_file():
            return file_path.read_text(encoding='utf-8')
    except Exception:
        pass
    return None


def _generate_fallback_diff(base_content: str | None, target_content: str | None, filepath: str) -> str:
    """Generate a unified diff as fallback when extraction fails."""
    import difflib

    base_lines = base_content.splitlines(keepends=True) if base_content else []
    target_lines = target_content.splitlines(keepends=True) if target_content else []

    diff = difflib.unified_diff(
        base_lines, target_lines,
        fromfile=f'a/{filepath}',
        tofile=f'b/{filepath}',
    )
    return ''.join(diff)


@rms.group(help='Change Analysis Commands')
def change():
    pass


@change.command('report', help='Generate change report between two revisions')
@click.pass_obj
@click.option('--base', required=True, help='Base Git revision (commit, tag, branch, HEAD, HEAD~N, or "working")')
@click.option('--target', required=True, help='Target Git revision (commit, tag, branch, HEAD, HEAD~N, or "working")')
@click.option('--output', 'output_path', default=None, help='Output directory or "console" for stdout')
@click.option('--include-non-artifact', is_flag=True, help='Include non-artifact text block changes')
@click.option('--single', is_flag=True, help='Generate a single consolidated report across all input records')
@click.option('--summary', is_flag=True, help='Generate abbreviated summary report (no content)')
@click.option('-f', '--config-file', type=click.Path(), default='.syntagmax/config.toml')
def change_report(
    obj: Params, base: str, target: str, output_path: str | None,
    include_non_artifact: bool, single: bool, summary: bool, config_file: Path,
):
    from datetime import datetime, timezone
    from syntagmax.change_worktree import (
        check_git_version, check_worktrees_gitignored,
        resolve_revision, validate_records_in_repo, worktree_pair,
    )
    from syntagmax.change_extract import extract_blocks_at_revision
    from syntagmax.change_diff import (
        get_changed_files, filter_changed_files,
        compare_artifacts, compare_text_blocks,
        compare_sidecar_artifacts,
    )
    from syntagmax.change_render import (
        render_change_report, render_summary_report,
        ChangeReportData, ExtractionError,
    )
    import git

    cfg_path = Path(config_file)
    if not cfg_path.exists():
        u.pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)

    config = Config(obj, cfg_path)

    # Open repo
    try:
        repo = git.Repo(config.base_dir(), search_parent_directories=True)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError) as e:
        u.pprint(f'[red]Error: Not a git repository: {e}[/red]')
        sys.exit(1)

    # Pre-flight checks
    check_git_version(repo)
    validate_records_in_repo(repo, config.input_records())

    worktree_base = config.root_dir() / 'worktrees'
    check_worktrees_gitignored(repo, worktree_base)

    # Compute offset from repo root to config.base_dir() for path resolution
    repo_root = Path(repo.working_tree_dir).resolve()
    base_dir_offset = config.base_dir().resolve().relative_to(repo_root)

    # Resolve revisions
    base_hash = resolve_revision(repo, base)
    target_hash = resolve_revision(repo, target)

    if base_hash == target_hash and base_hash != 'working':
        u.pprint('[yellow]Warning: Base and target resolve to the same revision. No changes expected.[/yellow]')

    # Default output path
    if output_path is None:
        output_path = '.syntagmax/reports/change/'

    # Determine short revision labels for filenames
    base_label = base_hash[:7] if base_hash != 'working' else 'working'
    target_label = target_hash[:7] if target_hash != 'working' else 'working'
    date_str = datetime.now().strftime('%Y%m%d')
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    with worktree_pair(repo, base_hash, target_hash, worktree_base) as (base_path, target_path):
        if base_hash != 'working' and target_hash != 'working':
            changed_files = get_changed_files(repo, base_hash, target_hash)
        else:
            # Diff against working tree: compare the non-working revision to HEAD working tree
            compare_hash = base_hash if target_hash == 'working' else target_hash
            changed_files = _get_working_tree_changed_files(repo, compare_hash)

        # Filter by input records
        if changed_files is not None:
            files_by_record = filter_changed_files(
                changed_files, config.input_records(), config.base_dir()
            )
        else:
            files_by_record = None

        # Extract blocks at both revisions
        changed_file_paths = [f.path for f in changed_files] if changed_files else None

        base_blocks, base_errors = extract_blocks_at_revision(config, base_path, changed_file_paths)
        target_blocks, target_errors = extract_blocks_at_revision(config, target_path, changed_file_paths)

        # Build extraction error objects with fallback diffs
        extraction_errors: list[ExtractionError] = []
        error_files = set(fp for fp, _ in base_errors) | set(fp for fp, _ in target_errors)
        for err_file in error_files:
            err_msgs = [msg for fp, msg in base_errors + target_errors if fp == err_file]
            # Generate fallback diff
            base_content = _read_file_safe(base_path, err_file)
            target_content = _read_file_safe(target_path, err_file)
            fallback = _generate_fallback_diff(base_content, target_content, err_file)
            extraction_errors.append(ExtractionError(
                file_path=err_file,
                error_message='; '.join(err_msgs),
                fallback_diff=fallback,
            ))

        # Generate reports per record
        reports: list[tuple[str, str]] = []  # (filename, markdown)

        record_names = set(base_blocks.keys()) | set(target_blocks.keys())
        if files_by_record:
            record_names |= set(files_by_record.keys())

        if not record_names:
            u.pprint('[yellow]No changes detected between the specified revisions.[/yellow]')
            return

        for record_name in sorted(record_names):
            base_recs = base_blocks.get(record_name, [])
            target_recs = target_blocks.get(record_name, [])
            file_diffs = files_by_record.get(record_name, []) if files_by_record else []

            # Compare artifacts
            artifact_diff = compare_artifacts(base_recs, target_recs)

            # Compare sidecar/binary artifacts
            binary_diff = compare_sidecar_artifacts(
                base_recs, target_recs, base_path, target_path, base_dir_offset,
            )

            # Compare text blocks if requested
            text_diff = None
            if include_non_artifact:
                text_diff = compare_text_blocks(base_recs, target_recs)

            # Build report data
            report_data = ChangeReportData(
                base_revision=base,
                target_revision=target,
                generated_at=generated_at,
                record_name=record_name,
                file_diffs=file_diffs,
                artifact_diff=artifact_diff,
                text_diff=text_diff,
                binary_diff=binary_diff,
                extraction_errors=[
                    e for e in extraction_errors if e.file_path in
                    {f.path for f in file_diffs} or not file_diffs
                ],
            )

            if summary:
                markdown = render_summary_report(report_data)
            else:
                markdown = render_change_report(report_data)

            # Build filename
            safe_name = record_name.replace(' ', '-').replace('/', '_').replace('\\', '_')
            suffix = '-summary' if summary else ''
            filename = f'{safe_name}-{base_label}-to-{target_label}-{date_str}{suffix}.md'
            reports.append((filename, markdown))

    # Write output
    if output_path == 'console':
        for filename, markdown in reports:
            if len(reports) > 1:
                print(f'\n--- {filename} ---\n')
            print(markdown)
    elif single and reports:
        # Consolidate all reports into one
        out_p = Path(output_path)
        if out_p.is_dir() or output_path.endswith('/') or output_path.endswith('\\'):
            out_p.mkdir(parents=True, exist_ok=True)
            suffix = '-summary' if summary else ''
            consolidated_name = f'change-{base_label}-to-{target_label}-{date_str}{suffix}.md'
            out_p = out_p / consolidated_name
        else:
            out_p.parent.mkdir(parents=True, exist_ok=True)

        combined = '\n\n---\n\n'.join(md for _, md in reports)
        out_p.write_text(combined, encoding='utf-8')
        u.pprint('[green]Change report generated:[/green]')
        u.pprint(f'  {out_p.absolute()}')
    else:
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        u.pprint('[green]Change report generated:[/green]')
        for filename, markdown in reports:
            file_path = out_dir / filename
            file_path.write_text(markdown, encoding='utf-8')
            u.pprint(f'  {file_path.absolute()}')


@rms.group(help='Project Editing Commands')
def edit():
    pass


@edit.command(help='Renumber artifact IDs')
@click.pass_obj
@click.argument(
    'config_path',
    type=click.Path(exists=True),
    default='.syntagmax/config.toml',
)
@click.option('--all', 'renumber_all', is_flag=True, help='Renumber all artifacts')
@click.option('--atype', help='Filter by artifact type')
@click.option('--schema', help='Custom ID schema')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without modifications')
def renumber(obj: Params, config_path: Path, renumber_all: bool, atype: str | None, schema: str | None, dry_run: bool):
    if not renumber_all and not atype:
        u.pprint('[red]Either --all or --atype must be specified.[/red]')
        return

    configurator = Config(obj, Path(config_path))
    renumber_artifacts(configurator, atype, schema, dry_run)


@edit.command('attrs', help='Add, remove, or replace attributes on artifacts in bulk')
@click.pass_obj
@click.option(
    '-f', '--config-file',
    type=click.Path(exists=True),
    default='.syntagmax/config.toml',
    help='Path to config file',
)
@click.option('-o', '--operation', type=click.Choice(['add', 'del', 'replace']), default='add', help='Operation to perform')
@click.option('-t', '--type', 'target_type', type=click.Choice(['attr', 'field']), default='attr', help='Target type: attr (YAML) or field (inline)')
@click.option('-n', '--name', default=None, help='Attribute name (omit for add to use metamodel mandatory attrs)')
@click.option('-l', '--value', default=None, help='Attribute value (defaults to TBD for add)')
@click.option('-s', '--section', required=True, help='Input record name')
@click.option('--csv', 'csv_path', type=click.Path(exists=True), default=None, help='CSV file for value lookup')
@click.option('--csv-id-column', default='id', help='CSV column for artifact ID matching')
@click.option('--csv-value-column', default='value', help='CSV column for attribute value')
@click.option('-d', '--csv-delimiter', default=',', help='CSV column delimiter')
@click.option('--dry-run', is_flag=True, help='Preview changes without modifying files')
def attrs(
    obj: Params,
    config_file: Path,
    operation: str,
    target_type: str,
    name: str | None,
    value: str | None,
    section: str,
    csv_path: str | None,
    csv_id_column: str,
    csv_value_column: str,
    csv_delimiter: str,
    dry_run: bool,
):
    # Validation
    if operation in ('del', 'replace') and name is None:
        u.pprint('[red]--name is required for del and replace operations.[/red]')
        return

    if operation == 'add' and name is None and value is not None:
        u.pprint('[red]Cannot specify --value without --name for metamodel-driven add.[/red]')
        return

    if operation == 'replace' and value is None and csv_path is None:
        u.pprint('[red]--value or --csv is required for replace operation.[/red]')
        return

    configurator = Config(obj, Path(config_file))

    # Load CSV mapping if provided
    csv_mapping = None
    if csv_path:
        csv_mapping = load_csv_mapping(
            Path(csv_path), csv_id_column, csv_value_column, csv_delimiter
        )

    manipulate_attributes(
        config=configurator,
        section=section,
        operation=operation,
        target_type=target_type,
        name=name,
        value=value,
        csv_mapping=csv_mapping,
        dry_run=dry_run,
    )


@edit.group(help='Fragment marker management commands')
def markers():
    pass


@markers.command('renumber', help='Assign sequential numeric IDs to unmarked fragment blocks')
@click.pass_obj
@click.argument(
    'config_path',
    type=click.Path(exists=True),
    default='.syntagmax/config.toml',
)
@click.option('--all', 'renumber_all', is_flag=True, help='Renumber across all input records')
@click.option('--section', default=None, help='Restrict to a specific input record')
@click.option('--marker', default=None, help='Only renumber blocks of a specific marker type')
@click.option('--dry-run', is_flag=True, help='Show planned changes without modifying files')
def markers_renumber(obj: Params, config_path: Path, renumber_all: bool, section: str | None, marker: str | None, dry_run: bool):
    if not renumber_all and not section:
        u.pprint('[red]Either --all or --section must be specified.[/red]')
        return

    if renumber_all and section:
        u.pprint('[red]Cannot specify both --all and --section.[/red]')
        return

    configurator = Config(obj, Path(config_path))
    renumber_markers(
        config=configurator,
        section=section,
        marker_filter=marker,
        dry_run=dry_run,
    )


@rms.group(help='MCP Server Management')
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
    configurator = Config(obj, Path(config_path))
    run_mcp_server(configurator, host, port, sse_path, transport)


@rms.group(help='Schema Management Commands')
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


def main():
    try:
        rms()

    except FatalError as e:
        u.pprint(f'[red]{len(e.errors)} fatal error(s): {e.errors[0]}[/red]')
        sys.exit(1)

    except RMSException as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        sys.exit(2)

    except Exception as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        traceback.print_exc()
        sys.exit(3)


if __name__ == '__main__':
    main()
