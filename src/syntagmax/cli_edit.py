# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Description: Syntagmax CLI - Edit commands.

from pathlib import Path

import click

import syntagmax.utils as u
from syntagmax.config import Config, Params
from syntagmax.edit import renumber_artifacts
from syntagmax.edit_attrs import manipulate_attributes, load_csv_mapping
from syntagmax.edit_markers import renumber_markers


@click.group(help='Project Editing Commands')
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
    '-f',
    '--config-file',
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
        csv_mapping = load_csv_mapping(Path(csv_path), csv_id_column, csv_value_column, csv_delimiter)

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
