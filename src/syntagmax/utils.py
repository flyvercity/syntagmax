# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-04-06
# Description: Utility functions for the RMS.

from graphlib import TopologicalSorter
from rich.console import Console

console = Console()


def pprint(what: str):
    console.print(what)  # type: ignore


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
