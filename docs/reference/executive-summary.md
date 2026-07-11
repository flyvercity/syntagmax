# Executive Summary: Syntagmax

## The Concept
Syntagmax is a Git-native Requirements Management System (RMS) that treats requirements as version-controlled artefacts alongside code. Traditional requirement management tools often live in silos, separate from the code and the developers who build the product. Syntagmax fundamentally changes this paradigm by storing, managing, and tracking requirements directly within Git repositories.

Using lightweight text formats (like Markdown) and integrating with popular tools (like Obsidian and VS Code), Syntagmax creates a unified environment where specifications and implementation evolve together in lockstep.

## Core Capabilities
- **Single Source of Truth:** Manages requirements directly within the Git repository, leveraging Git's powerful version control for auditing, branching, and historical tracking.
- **Automated Traceability & Impact Analysis:** Automatically extracts revision history and tracks parent-child dependencies across different artifacts (e.g., from high-level features down to source code sections). If a parent requirement changes, Syntagmax flags downstream artifacts that may be impacted.
- **Traceability Matrix Export:** Exports compliance-ready traceability matrices (CSV/TSV) between artifact types, with configurable direction, flat mode, and plugin-delegated export — directly integrable into audit and certification workflows.
- **Customizable Metamodels:** Features a domain-specific language (DSL) to define strict rules for artifacts, ensuring consistency, required attributes, and valid links across the project.
- **Structured Document Publishing:** Generates formatted Markdown documents from requirements with optional DOCX and PDF export via Pandoc. A plugin system enables custom transformations, pre-filters, and export hooks, supporting enterprise documentation workflows without leaving the Git ecosystem.
- **AI-Powered Collaboration:** Integrates AI at two levels: (1) an analysis step that uses LLMs (Anthropic Claude, AWS Bedrock) to review requirements for quality, completeness, and consistency; and (2) a Model Context Protocol (MCP) server enabling AI agents to query, navigate, and reason over the full requirements set in real time.
- **Bulk Editing & Governance:** Provides batch operations for renumbering artifact IDs (with configurable schemas) and manipulating attributes across entire sections — including CSV-driven imports — ensuring large-scale governance actions remain atomic, auditable, and Git-tracked.
- **Extensible Plugin Architecture:** A hook-based plugin system (local files or installable packages) allows organisations to inject custom block transforms, markdown post-processing, pre-publishing filters, and trace export formats without forking the core tool.
- **Frictionless Developer Experience:** Avoids proprietary databases and heavy enterprise software. It integrates seamlessly into existing CI/CD pipelines, IDEs, and local workflows.

## Business Value
**1. Accelerated Time-to-Market:** By eliminating the friction of switching contexts (from external requirements tools to code editors), engineering teams can execute faster with absolute clarity on what needs to be built.

**2. Reduced Compliance and Quality Risks:** Automated impact analysis ensures that whenever a core specification changes, every related implementation detail is flagged for review. This structural integrity minimises missed requirements and costly late-stage bugs.

**3. Future-Proofing with AI:** The native MCP server and AI analysis pipeline enable organisations to instantly leverage AI tools to analyse requirements, generate test cases, or review code against specifications, creating a massive multiplier in team productivity.

**4. Lower Operational Overhead:** Syntagmax removes the need for expensive, disconnected, and heavy enterprise requirements software by shifting the paradigm to tools that engineers already use and love.

**5. Standards & Certification Readiness:** Traceability matrices, structured document export, and metamodel-enforced attribute completeness provide direct evidence artefacts for safety and quality standards (DO-178C, ISO 26262, IEC 62304) — reducing certification preparation time from weeks to minutes.

Syntagmax transforms product requirements from static, disconnected documents into a living, verifiable, and intelligent part of the software development lifecycle.
