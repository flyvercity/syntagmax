# Technical Summary: Syntagmax Capabilities

Syntagmax is a Git-native Requirements Management System (RMS) designed for high-integrity software development. It treats requirements and other project artefacts as first-class citizens of the version control system, enabling seamless integration between specifications and implementation.

## 1. Git-Native Architecture
- **Single Source of Truth:** Artefacts are stored directly in the Git repository alongside source code.
- **Native Versioning:** Leverages Git for history, branching, merging, and auditing of requirements.
- **Revision Extraction:** Automatically associates artefacts with Git commit metadata (hash, author, timestamp) using `git blame`.
- **Dirty Worktree Detection:** Optionally enforces clean worktree state before analysis to guarantee reproducible results.

## 2. Multi-Source Extraction
Syntagmax supports a variety of input formats through a modular driver system:
- **Obsidian:** Extracts requirements from Markdown files with YAML frontmatter. Supports configurable element exclusion (callouts, headings, horizontal rules, frontmatter, tags) with fine-grained removal modes (`only`, `string`, `string-on-start`). Fragment markers allow non-artefact text blocks (design rationale, notes) to be preserved alongside requirements. Integrates with Obsidian vault settings for attachment folder resolution.
- **Markdown:** Parses custom requirement blocks within standard Markdown documents.
- **IPYNB:** Extracts artefacts from Jupyter Notebook cells.
- **Source Code (Text):** Identifies requirements embedded in source code via special comment markers, parsed using a Lark grammar for structured extraction with ID references and inline attributes.
- **Sidecar:** Supports binary artefacts (e.g., images, diagrams) with associated YAML metadata files. Revision history spans both the primary file and the sidecar.

## 3. Metamodeling DSL
The system uses a custom Domain-Specific Language (DSL) to define the project's data model:
- **Artifact Definition:** Define custom artefact types (e.g., REQ, SYS, ARCH).
- **Attribute Validation:** Specify mandatory/optional attributes with types (string, integer, boolean, enum, reference).
- **Multivalued Enums:** Support for enum types that allow multiple selections (e.g., `attribute allocation is mandatory multiple enum [HW, SW]`).
- **Schema Enforcement:** Validate artefact IDs against custom patterns (e.g., `REQ-{num:3}`).
- **Multiple Values:** Support for attributes with multiple values (e.g., tags, authors).
- **Trace Declarations:** Define traceability relationships between artefact types with cardinality (mandatory/optional) and analysis mode (`via commit` or `via timestamp`).

## 4. Traceability & Impact Analysis
- **Hierarchical Relationships:** Establish parent-child links between artefacts.
- **Revision Pinning:** Explicitly link an artefact to a specific revision of its parent (e.g., `parent: REQ-001@c2d94e4`).
- **Impact Detection:** Automatically identifies "suspicious" links when a parent is updated without a corresponding update in the child artefact. Uses exact hash comparison (7-char short or full 40-char) by design.
- **Analysis Modes:** Supports both `via commit` (precise) and `via timestamp` (heuristic) impact analysis.
- **Traceability Matrix Export:** Generates forward (child→parent) and reverse (parent→child) traceability matrices as CSV/TSV. Uses left outer join semantics to ensure every lead artefact appears, highlighting coverage gaps. Supports flat mode (semicolon-separated multi-links), additional attribute columns, and plugin-based export for custom formats.

## 5. AI Integration & MCP Server
- **Model Context Protocol (MCP):** Exposes requirements to AI agents and LLMs via a standard protocol (stdio and SSE transports), enabling automated analysis and reasoning.
- **Multi-Provider Support:** Integrates with Ollama (local), Anthropic (Claude), OpenAI, Google Gemini, and AWS Bedrock. API keys configurable via config file or environment variables. Per-provider timeout control.
- **AI-Assisted Analysis:** Built-in pipeline step that uses LLMs for requirement verification, consistency checks, and quality analysis.

## 6. DAG-Based Processing Pipeline
Internal execution is managed by a Directed Acyclic Graph (DAG) that ensures efficient and correct processing:
- **Topological Sorting:** Automatically determines the execution order based on task dependencies.
- **Modular Steps:** Pipeline includes extraction, artefact map building, PID population, tree building, tree analysis, revision population, impact analysis, metrics calculation, and AI processing.
- **Target-Driven Execution:** Users request a target step; the engine resolves and executes only the required dependencies.
- **Public Steps:** Five user-facing targets (`extract`, `tree`, `impact`, `metrics`, `ai`) backed by internal intermediate steps.

## 7. Metrics & Reporting
- **Polars-Based Analysis:** Metrics are calculated using Polars DataFrames for efficient aggregation across large artefact sets.
- **Coverage Analysis:** Calculates verification coverage percentage and identifies requirements missing verification methods.
- **TBD Detection:** Identifies artefacts with incomplete ("TBD") attribute values and reports the percentage.
- **Status Distribution:** Aggregates requirement counts by lifecycle status (Draft, Active, Retired, etc.).
- **Structured Report:** Outputs a unified Markdown report combining errors, artefact tree (optional), metrics, impact analysis, and AI results. Supports file output or stdout.

## 8. Document Publishing Pipeline
- **Block Tree Architecture:** The publishing engine builds an intermediate block tree (artefacts, text blocks, error blocks) from extracted content, enabling transformations before rendering.
- **Multi-Record Publishing:** Supports publishing individual records to separate files or consolidating all records into a single document.
- **Image Manifest:** Tracks and copies image assets referenced by artefacts, with stale image cleanup on each publish cycle. Resolves Obsidian `![[image]]` references via vault attachment path settings.
- **Pandoc Integration:** Converts Markdown output to DOCX or PDF via Pandoc, with configurable reference document templates and resource path resolution.
- **Date-Suffixed Outputs:** Supports appending date stamps to filenames for versioned document releases.

## 9. Plugin System
- **Hook-Based Architecture:** Plugins implement one or more hooks: `transform_blocks` (modify the block tree), `transform_markdown` (post-process rendered output), `filter_block` (per-block pre-publishing filter), `export_trace` (custom tracing export format).
- **Discovery Modes:** Plugins are loaded from local Python files (`plugins/<name>.py` or `plugins/<name>/`) or from installed packages (entry point discovery).
- **Configuration:** Declared in `config.toml` via `[[plugin]]` blocks with per-plugin parameters, execution order by declaration order, and individual enable/disable toggles.
- **Validation:** Plugin names are validated against path traversal. Missing or broken plugins raise fatal errors at load time.

## 10. Bulk Editing Operations
- **ID Renumbering:** Renumbers artefact IDs across the project according to configurable schemas with macro expansion (`{atype}`, `{num:N}`). Stable ordering via file-path sort.
- **Attribute Manipulation:** Adds, removes, or replaces YAML attributes or inline fields across entire input sections. Supports metamodel-driven insertion of all mandatory attributes.
- **CSV-Driven Import:** Values can be sourced from CSV files with configurable ID and value column mapping, enabling integration with external tools (DOORS, Jira exports).
- **Atomic Writes:** All changes are computed in memory before writing, ensuring no partial updates on failure.
- **Dry Run:** Every editing operation supports `--dry-run` for safe preview.

## 11. Schema Generation & Configuration
- **Pydantic-Validated Configuration:** The entire configuration model (`config.toml`, `publish.yaml`) is defined as Pydantic models with strict validation, typed fields, and descriptive metadata.
- **JSON Schema Export:** Generates JSON Schema for both the main project configuration and the publishing configuration via `syntagmax schema config` and `syntagmax schema publish`.
- **IDE Integration:** Exported schemas enable autocompletion and validation in editors that support JSON Schema for TOML/YAML files.
- **Global Configuration:** Supports a user-level global config (`~/.config/syntagmax/config.toml`). Parse errors in global config are intentionally fatal.
