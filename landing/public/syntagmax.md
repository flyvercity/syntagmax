# Syntagmax — Git-Based Requirements Management System

> Lightweight traceability, change detection, and impact analysis — fully native to your Git workflow.

Syntagmax is a product by [Flyvercity](https://flyvercity.com).

This is the Markdown version of the Syntagmax landing page (the "For Agents" view), provided for AI agents and crawlers under the [llms.txt](https://llmstxt.org) convention.

---

## What it is

Syntagmax is a command-line requirements-management and traceability system that treats your Git repository as the single source of truth. It extracts artifacts from your repository, validates them against a declarative metamodel, computes traceability metrics, and generates comprehensive reports — without any external database.

## Features

- **Git-Native** — built on `git blame` and history. No external databases; your repository is the single source of truth.
- **Metamodel DSL** — define artifact types, attributes, and trace rules declaratively with a simple, readable syntax.
- **Impact Analysis** — detect changes and propagate impact across the traceability tree automatically.
- **Traceability** — export full traceability matrices as CSV/TSV, and verify coverage with forward, reverse, and flat modes.
- **Task Generation** — automatically create verification tasks from impact analysis, so review work is tracked without manual bookkeeping.
- **AI Agent Verification** — integrate local AI agents (Kiro, Claude, Copilot, and more than ten others) for impact-task verification, automated artifact amendments, and ad-hoc commands.

## How it works

Point Syntagmax at your repository. It extracts artifacts, validates them against your metamodel, computes traceability metrics, and generates reports — all from the command line. The repository stays the source of truth: Syntagmax reads Git history for change detection and writes reports, static-verification results, and AI insights back out as outputs.

## Install

Syntagmax is published on PyPI:

```
pip install syntagmax
```

## Links

- [PyPI package](https://pypi.org/project/syntagmax/)
- [GitHub repository](https://github.com/flyvercity/syntagmax)
- [VS Code extension](https://github.com/flyvercity/syntagmax-vscode)
- [Flyvercity (company)](https://flyvercity.com)

© 2026 Flyvercity · MIT License
