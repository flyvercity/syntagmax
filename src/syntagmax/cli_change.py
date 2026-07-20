# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: Syntagmax CLI - Change analysis commands.

import sys
from pathlib import Path

import click

import syntagmax.utils as u
from syntagmax.config import Config, Params


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
        base_lines,
        target_lines,
        fromfile=f'a/{filepath}',
        tofile=f'b/{filepath}',
    )
    return ''.join(diff)


@click.group(help='Change Analysis Commands')
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
    obj: Params,
    base: str,
    target: str,
    output_path: str | None,
    include_non_artifact: bool,
    single: bool,
    summary: bool,
    config_file: Path,
):
    from datetime import datetime, timezone
    from syntagmax.change_worktree import (
        check_git_version,
        check_worktrees_gitignored,
        resolve_revision,
        validate_records_in_repo,
        worktree_pair,
    )
    from syntagmax.change_extract import extract_blocks_at_revision
    from syntagmax.change_diff import (
        get_changed_files,
        get_working_tree_changed_files,
        filter_changed_files,
        compare_artifacts,
        compare_text_blocks,
        compare_sidecar_artifacts,
    )
    from syntagmax.change_render import (
        render_change_report,
        render_summary_report,
        ChangeReportData,
        ExtractionError,
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
            changed_files = get_working_tree_changed_files(repo, compare_hash)

        # Filter by input records
        if changed_files is not None:
            files_by_record = filter_changed_files(changed_files, config.input_records(), config.base_dir())
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
            extraction_errors.append(
                ExtractionError(
                    file_path=err_file,
                    error_message='; '.join(err_msgs),
                    fallback_diff=fallback,
                )
            )

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
                base_recs,
                target_recs,
                base_path,
                target_path,
                base_dir_offset,
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
                extraction_errors=[e for e in extraction_errors if e.file_path in {f.path for f in file_diffs} or not file_diffs],
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


@change.command('baseline', help='Create a baseline tag across all affected repositories')
@click.pass_obj
@click.argument('tag_name')
@click.option('-m', '--message', default='Baseline created by Syntagmax', help='Tag annotation message')
@click.option('--force', is_flag=True, help='Overwrite existing tags')
@click.option('--dry-run', is_flag=True, help='Preview actions without creating tags')
@click.option('-f', '--config-file', type=click.Path(), default='.syntagmax/config.toml')
def change_baseline(obj: Params, tag_name: str, message: str, force: bool, dry_run: bool, config_file: str):
    from syntagmax.change_baseline import (
        discover_repos,
        check_repos_clean,
        validate_tag_name,
        check_tag_exists,
        create_baseline_tag,
    )

    cfg_path = Path(config_file)
    if not cfg_path.exists():
        u.pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)

    config = Config(obj, cfg_path)

    # Discover repos from all input records
    repos = discover_repos(config.input_records(), config.base_dir())

    # Pre-flight validations
    check_repos_clean(repos)
    validate_tag_name(tag_name, config.baseline_config.tag_pattern)
    check_tag_exists(tag_name, repos, force)

    # Dry-run: print plan and exit
    if dry_run:
        u.pprint('[cyan]Dry run — no tags will be created.[/cyan]')
        u.pprint(f'  Tag name: {tag_name}')
        u.pprint(f'  Message: {message}')
        u.pprint(f'  Repositories ({len(repos)}):')
        for repo_root, repo in repos.items():
            head_short = repo.head.commit.hexsha[:7]
            u.pprint(f'    - {repo_root} (HEAD: {head_short})')
        return

    # Create tags
    results = create_baseline_tag(tag_name, repos, message, force)

    # Success output
    u.pprint(f'[green]Baseline "{tag_name}" created in {len(results)} repository(ies):[/green]')
    for repo_root, commit_short in results:
        u.pprint(f'  - {repo_root} @ {commit_short}')
    u.pprint('')
    u.pprint('[yellow]Remember to push the tag to your remotes:[/yellow]')
    for repo_root, _ in results:
        u.pprint(f'  cd {repo_root} && git push origin {tag_name}')
