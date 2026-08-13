# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Utility functions for the RMS.

from graphlib import TopologicalSorter
from typing import TYPE_CHECKING
from rich.console import Console

if TYPE_CHECKING:
    from syntagmax.config import Config

console = Console()


def pprint(what: str):
    console.print(what)  # type: ignore


def load_config_or_exit(obj, config_file) -> 'Config':
    """
    Safely load project configuration or exit with code 1 if the configuration file is missing.
    """
    import sys
    from pathlib import Path
    from syntagmax.config import Config

    cfg_path = Path(config_file)
    if not cfg_path.exists():
        pprint(f'[red]Error: Configuration file "{cfg_path}" does not exist.[/red]')
        sys.exit(1)

    return Config(obj, cfg_path)


def get_execution_plan(all_dependencies, final_step):
    """
    Returns an ordered list of steps required to reach final_step.
    """
    required_steps = {final_step}
    to_process = [final_step]

    # Trace backwards to find all dependencies
    while to_process:
        current = to_process.pop()
        deps = all_dependencies.get(current, set())
        for dep in deps:
            if dep not in required_steps:
                required_steps.add(dep)
                to_process.append(dep)

    # Create a subgraph containing only the required steps
    filtered_deps = {step: all_dependencies.get(step, set()) & required_steps for step in required_steps}

    ts = TopologicalSorter(filtered_deps)
    return list(ts.static_order())
