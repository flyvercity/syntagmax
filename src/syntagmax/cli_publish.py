# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: Syntagmax CLI - Publish command.

import logging as lg
import sys
from pathlib import Path

import click

import syntagmax.utils as u
from syntagmax.config import Config, Params


def _run_pandoc_conversion(md_path: Path, docx: bool, pdf: bool, reference_doc: Path | None = None) -> bool:
    """Run Pandoc conversion for the given Markdown file."""
    from syntagmax.pandoc import convert

    formats = []
    if docx:
        formats.append(('docx', md_path.with_suffix('.docx')))
    if pdf:
        formats.append(('pdf', md_path.with_suffix('.pdf')))

    success_all = True
    for fmt, out_path in formats:
        success, message = convert(md_path, out_path, fmt, reference_doc=reference_doc if fmt == 'docx' else None, resource_path=md_path.parent)
        if success:
            u.pprint(f'[green]Converted to {fmt.upper()}: {out_path}[/green]')
        else:
            u.pprint(f'[yellow]Pandoc conversion to {fmt.upper()} failed: {message}[/yellow]')
            success_all = False
    return success_all


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


@click.command(help='Publish project to markdown document(s)')
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
    obj: Params,
    records: tuple[str, ...],
    publish_all: bool,
    single: bool,
    output_path: str | None,
    config_file: Path,
    date_suffix: bool,
    docx: bool,
    pdf: bool,
    docx_template_path: str | None,
    pre_filter_name: str | None,
):
    from datetime import datetime
    from syntagmax.publish import build_block_tree, render_block_tree
    from syntagmax.blocks import ArtifactBlock, TextBlock
    from syntagmax.plugin import run_block_transforms, run_markdown_transforms, find_plugin_by_name, run_pre_filter

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
            if not _run_pandoc_conversion(out_p, docx, pdf, reference_doc=reference_doc):
                sys.exit(1)
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
            conversion_failed = False
            for file_path, record in published_files:
                reference_doc = _resolve_template_for_record(record) if docx else None
                if not _run_pandoc_conversion(file_path, docx, pdf, reference_doc=reference_doc):
                    conversion_failed = True
            if conversion_failed:
                sys.exit(1)
