# Technical Summary: Syntagmax Capabilities

Syntagmax is a Git-native Requirements Management System (RMS) designed for high-integrity software development. It treats requirements and other project artifacts as first-class citizens of the version control system, enabling seamless integration between specifications and implementation.

## 1. Git-Native Architecture
- **Single Source of Truth:** Artifacts are stored directly in the Git repository alongside source code.
- **Native Versioning:** Leverages Git for history, branching, merging, and auditing of requirements.
- **Revision Extraction:** Automatically associates artifacts with Git commit metadata (hash, author, timestamp) using `git blame`.

## 2. Multi-Source Extraction
Syntagmax supports a variety of input formats through a modular driver system:
- **Obsidian:** Extracts requirements from Markdown files with YAML frontmatter.
- **Markdown:** Parses custom requirement blocks within standard Markdown documents.
- **IPYNB:** Extracts artifacts from Jupyter Notebook cells.
- **Source Code (Text):** Identifies requirements embedded in source code via special comment markers.
- **Sidecar:** Supports binary artifacts (e.g., images) with associated metadata files.

## 3. Metamodeling DSL
The system uses a custom Domain-Specific Language (DSL) to define the project's data model:
- **Artifact Definition:** Define custom artifact types (e.g., REQ, SYS, ARCH).
- **Attribute Validation:** Specify mandatory/optional attributes with types (string, integer, boolean, enum, reference).
- **Schema Enforcement:** Validate artifact IDs against custom patterns (e.g., `REQ-{num:3}`).
- **Multiple Values:** Support for attributes with multiple values (e.g., tags, authors).

## 4. Traceability & Impact Analysis
- **Hierarchical Relationships:** Establish parent-child links between artifacts.
- **Revision Pinning:** Explicitly link an artifact to a specific revision of its parent (e.g., `parent: REQ-001@c2d94e4`).
- **Impact Detection:** Automatically identifies "suspicious" links when a parent is updated without a corresponding update in the child artifact.
- **Analysis Modes:** Supports both `via commit` (precise) and `via timestamp` (heuristic) impact analysis.

## 5. AI Integration & MCP Server
- **Model Context Protocol (MCP):** Exposes requirements to AI agents and LLMs via a standard protocol, enabling automated analysis and reasoning.
- **Multi-Provider Support:** Integrates with OpenAI, Anthropic, Google Gemini, Ollama, and AWS Bedrock.
- **AI-Assisted Analysis:** Built-in capabilities for requirement verification and consistency checks using LLMs.

## 6. DAG-Based Processing Pipeline
Internal execution is managed by a Directed Acyclic Graph (DAG) that ensures efficient and correct processing:
- **Topological Sorting:** Automatically determines the execution order based on task dependencies.
- **Modular Steps:** Pipeline includes extraction, tree building, revision population, impact analysis, metrics calculation, and AI processing.
- **Scalability:** The dependency-aware engine ensures that only necessary steps are executed for a given target.

## 7. Metrics & Reporting
- **Coverage Analysis:** Calculates requirement coverage and identifies gaps.
- **Status Tracking:** Monitors the lifecycle of artifacts (e.g., Draft, Active, Retired).
- **Extensible Templates:** Generates reports in various formats (Rich console output, Markdown) using Jinja2 templates.
