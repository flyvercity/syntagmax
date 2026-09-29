# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-09-28
# Description: Library-first embedding facade for Syntagmax (read + analyse + write).

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syntagmax.artifact import Artifact, ArtifactMap, Revision
from syntagmax.config import Config, InputRecord
from syntagmax.params import Params
from syntagmax.report import ReportError

from syntagmax.extract import extract, build_artifact_map, EXTRACTORS
from syntagmax.tree import build_tree, populate_pids
from syntagmax.analyse import analyse_tree
from syntagmax.extractors.extractor import Extractor


@dataclass
class Options:
    """Library-facing options with defaults matching the current CLI defaults.

    The host constructs an ``Options`` and never touches the CLI-shaped
    ``Params`` ``TypedDict``; the facade owns the translation (R1.2, R1.3).
    """

    render_tree: bool = False
    no_git: bool = False
    allow_dirty_worktree: bool = False
    suppress_tracing: bool = False
    tasks: bool = False
    language: str = 'en'
    warnings_as_errors: bool = False
    log_level: str | None = None


@dataclass
class ArtifactView:
    """Structured, public read view over an internal :class:`Artifact` (R1.5).

    Distinct from the internal ``Artifact`` so the facade has a stable public
    contract without freezing the core representation. Serialisation is the
    host's responsibility.
    """

    aid: str
    atype: str
    fields: dict[str, str | list[str]]
    parents: list[dict[str, object]]
    children: list[str]
    latest_revision: Revision | None
    #: The artifact's Markdown body (``contents``), exposed for host rendering
    #: and editing. Optional and defaulted so the public contract stays
    #: backwards-compatible for callers that construct an ``ArtifactView``
    #: without a body.
    body: str | None = None


@dataclass
class Diagnostic:
    """Public, structured representation of a single analysis issue (R2).

    This is the host-facing projection of the core's :class:`ReportError`;
    the facade owns the ``ReportError -> Diagnostic`` mapping (X1) so hosts
    never parse flat diagnostic strings. See :meth:`Session.analyse`.
    """

    severity: str
    artifact_id: str | None
    rule: str | None
    category: str
    location: str
    message: str


@dataclass
class AnalysisResult:
    """Structured result of :meth:`Session.analyse` (R1.6).

    ``metrics`` and ``impact`` are passed through unchanged from the core
    :class:`~syntagmax.report.Report` (``benedict`` or ``None``); the host is
    free to serialise them as it sees fit.
    """

    diagnostics: list[Diagnostic]
    metrics: Any
    impact: Any


@dataclass
class TraceResult:
    """Structured, public result of :meth:`Session.trace` (R1).

    A stable public projection of the core :class:`~syntagmax.trace.TraceMatrix`
    so hosts never touch core internals: ``header`` is the column labels (with
    ``ChildID``/``ParentID`` ordered per ``direction``), ``rows`` are the cell
    values in header order, and ``record_names`` maps each referenced artifact
    id to its input-record name. Render a delimited string via
    :func:`render_trace`.
    """

    direction: str
    child_type: str
    parent_type: str
    header: list[str]
    rows: list[list[str]]
    record_names: dict[str, str]


@dataclass
class PublishResult:
    """Structured, public result of :meth:`Session.publish` (R2).

    ``markdown`` is the consolidated, all-records single-file publication;
    ``artifact_count``/``text_block_count`` summarise what was compiled. Phase A
    is Markdown-only (no Pandoc/DOCX/PDF, no image-manifest side effects).
    """

    markdown: str
    artifact_count: int
    text_block_count: int


def render_trace(result: TraceResult, *, delimiter: str = ',') -> str:
    """Render a :class:`TraceResult` as a delimited string (CSV or TSV) (R1).

    Reuses :func:`syntagmax.trace.render_trace_csv` by reconstructing a minimal
    :class:`~syntagmax.trace.TraceMatrix` from the public result, so the host
    obtains an identical rendering to the ``trace`` CLI without re-running the
    pipeline. ``delimiter`` is ``','`` for CSV or ``'\\t'`` for TSV.
    """
    from syntagmax.trace import TraceMatrix, TraceRecord, render_trace_csv

    # The first three header columns are fixed (RecordNumber + the two ID
    # columns); any trailing columns are attribute names.
    attribute_names = list(result.header[3:])
    matrix = TraceMatrix(
        direction=result.direction,
        child_type=result.child_type,
        parent_type=result.parent_type,
        attribute_names=attribute_names,
        record_names=dict(result.record_names),
    )
    for row in result.rows:
        record_number = int(row[0]) if row and str(row[0]).isdigit() else len(matrix.records) + 1
        lead_id = row[1] if len(row) > 1 else ''
        linked_id = row[2] if len(row) > 2 else ''
        attributes = {name: (row[3 + i] if 3 + i < len(row) else '') for i, name in enumerate(attribute_names)}
        matrix.records.append(
            TraceRecord(
                record_number=record_number,
                lead_id=lead_id,
                linked_id=linked_id,
                attributes=attributes,
            )
        )
    return render_trace_csv(matrix, delimiter=delimiter)


def _options_to_params(options: Options, cwd: str) -> Params:
    """Translate library-facing :class:`Options` into a CLI-shaped ``Params``.

    Every required ``Params`` key is populated (note ``ai`` and ``cwd`` are
    required by the ``TypedDict``); ``log_level`` and ``warnings_as_errors``
    are ``NotRequired`` but always supplied here for determinism.
    """

    params: Params = {
        'render_tree': options.render_tree,
        'ai': False,
        'cwd': cwd,
        'no_git': options.no_git,
        'allow_dirty_worktree': options.allow_dirty_worktree,
        'language': options.language,
        'suppress_tracing': options.suppress_tracing,
        'tasks': options.tasks,
        'warnings_as_errors': options.warnings_as_errors,
    }

    if options.log_level is not None:
        params['log_level'] = options.log_level

    return params


def _diagnostic_from_error(e: ReportError) -> Diagnostic:
    """Map a core :class:`ReportError` to a public :class:`Diagnostic` (X1).

    The mapping is fixed and exact: ``rule`` falls back to ``category`` when
    unset; ``location`` combines ``file_path`` and ``line_range`` when both are
    present, otherwise it is ``file_path`` (or an empty string).
    """

    if e.file_path and e.line_range:
        location = f'{e.file_path}:{e.line_range[0]}-{e.line_range[1]}'
    else:
        location = e.file_path or ''

    return Diagnostic(
        severity=e.severity,
        artifact_id=e.artifact_id,
        rule=e.rule or e.category,
        category=e.category,
        location=location,
        message=e.message,
    )


def open_project(config_path: str | Path, *, options: Options | None = None) -> 'Session':
    """Open a Syntagmax project and return a :class:`Session` (R1.1).

    ``FatalError`` / ``RMSException`` propagate unchanged out of this call and
    all :class:`Session` methods (R1.8); the facade never swallows them.
    """

    if options is None:
        options = Options()

    resolved = Path(config_path).resolve()
    params = _options_to_params(options, str(resolved.parent))
    config = Config(params, Path(config_path))
    return Session(config)


class Session:
    """A synchronous, thread-safe read handle over a populated project.

    ``artifacts()`` wraps the canonical read sequence
    ``extract -> build_artifact_map -> populate_pids -> build_tree ->
    analyse_tree`` exactly once and caches the result. An internal
    ``threading.Lock`` guards the cache so a multi-threaded host sharing a
    single ``Session`` cannot race on cache invalidation (E2).

    Known trade-off: ``reload()`` re-runs the full pipeline; for very large
    repositories a single-artifact write incurs a full re-parse. This is an
    accepted Phase-1 limitation (incremental reload is future work).
    """

    def __init__(self, config: Config):
        self._config = config
        self._lock = threading.Lock()
        self._cache: ArtifactMap | None = None

    def _load(self) -> ArtifactMap:
        """Compute the populated :class:`ArtifactMap` under the lock, once."""
        with self._lock:
            if self._cache is None:
                errors: list = []
                artifacts_list = extract(self._config, errors)
                artifacts = build_artifact_map(artifacts_list, errors)
                populate_pids(self._config, artifacts, errors)
                build_tree(self._config, artifacts, errors)
                analyse_tree(self._config, artifacts, errors)
                self._cache = artifacts
            return self._cache

    def reload(self) -> None:
        """Force recomputation after a write by clearing the cache (E2)."""
        with self._lock:
            self._cache = None

    def artifacts(self) -> ArtifactMap:
        """Return the populated artifact graph (R1.4)."""
        return self._load()

    def _to_view(self, artifact: Artifact) -> ArtifactView:
        parents = [
            {
                'pid': link.pid,
                'nominal_revision': link.nominal_revision,
                'is_suspicious': link.is_suspicious,
            }
            for link in artifact.parent_links
        ]
        # Copy the fields mapping (including nested list values) so a host that
        # mutates the returned view cannot corrupt the cached artifact.
        fields: dict[str, str | list[str]] = {
            key: list(value) if isinstance(value, list) else value for key, value in artifact.fields.items()
        }
        return ArtifactView(
            aid=artifact.aid,
            atype=artifact.atype,
            fields=fields,
            parents=parents,
            children=sorted(artifact.children),
            latest_revision=artifact.latest_revision,
            body=artifact.contents(),
        )

    def get(self, aid: str) -> ArtifactView | None:
        """Return the :class:`ArtifactView` for ``aid`` or ``None`` (R1.5)."""
        artifacts = self._load()
        artifact = artifacts.get(aid)
        if artifact is None:
            return None
        return self._to_view(artifact)

    def query(self, *, atype: str | None = None) -> list[ArtifactView]:
        """Return views, optionally filtered by ``atype`` (R1.5).

        The synthetic ``ROOT`` pseudo-artifact is excluded.
        """
        artifacts = self._load()
        views: list[ArtifactView] = []
        for artifact in artifacts.values():
            if artifact.atype == 'ROOT':
                continue
            if atype is not None and artifact.atype != atype:
                continue
            views.append(self._to_view(artifact))
        return views

    def search(self, q: str) -> list[ArtifactView]:
        """Case-insensitive search with AND semantics (R1.5, P2).

        Matches against ``aid``, ``atype``, and all ``fields`` including the
        ``contents`` body text. A multi-term query matches only when every
        whitespace-separated term is found across those searchable strings.
        """
        terms = q.lower().split()
        artifacts = self._load()
        results: list[ArtifactView] = []

        for artifact in artifacts.values():
            if artifact.atype == 'ROOT':
                continue

            haystack_parts: list[str] = [artifact.aid, artifact.atype]
            for value in artifact.fields.values():
                if isinstance(value, list):
                    haystack_parts.extend(str(v) for v in value)
                else:
                    haystack_parts.append(str(value))

            haystack = '\n'.join(haystack_parts).lower()

            if all(term in haystack for term in terms):
                results.append(self._to_view(artifact))

        return results

    # --- Analysis (R1.6) ---------------------------------------------------

    def analyse(self) -> AnalysisResult:
        """Run the analysis path and return structured diagnostics (R1.6).

        Delegates to ``main.process('metrics', config)`` — whose DAG includes
        ``impact`` and ``metrics`` — then converts every ``Report.errors``
        entry to a public :class:`Diagnostic` and passes ``metrics``/``impact``
        through unchanged. ``FatalError``/``RMSException`` propagate (R1.8).
        """
        from syntagmax import main

        report = main.process('metrics', self._config)
        diagnostics = [_diagnostic_from_error(ReportError.from_any(e)) for e in report.errors]
        return AnalysisResult(diagnostics=diagnostics, metrics=report.metrics, impact=report.impact)

    # --- Traceability (R1) -------------------------------------------------

    def trace(
        self,
        child_type: str,
        parent_type: str,
        *,
        direction: str = 'forward',
        attributes: list[str] | None = None,
        flat: bool = False,
    ) -> TraceResult:
        """Build a traceability matrix and return a public result (R1).

        Orchestrates the same computation the ``trace`` CLI runs, but reuses the
        cached, already-populated :class:`ArtifactMap` obtained via
        :meth:`_load` (which acquires ``self._lock``) rather than re-running
        ``extract`` from scratch (E1): ``build_trace_matrix`` operates on that
        shared map, so a multi-threaded host never races the read cache nor
        duplicates disk I/O. ``FatalError``/``RMSException`` propagate (R1.8).
        """
        from syntagmax.trace import build_trace_matrix, render_trace_csv

        artifacts = self._load()
        matrix = build_trace_matrix(
            artifacts=artifacts,
            child_type=child_type,
            parent_type=parent_type,
            direction=direction,
            attributes=list(attributes) if attributes else [],
            flat=flat,
        )

        # Derive the header identically to render_trace_csv so header/rows stay
        # in lock-step with the CSV rendering.
        rendered = render_trace_csv(matrix, delimiter='\x00')
        header_line = rendered.split('\n', 1)[0]
        header = header_line.split('\x00') if header_line else []

        rows: list[list[str]] = []
        for record in matrix.records:
            row = [str(record.record_number), record.lead_id, record.linked_id]
            row.extend(record.attributes.get(name, '') for name in matrix.attribute_names)
            rows.append(row)

        return TraceResult(
            direction=matrix.direction,
            child_type=matrix.child_type,
            parent_type=matrix.parent_type,
            header=header,
            rows=rows,
            record_names=dict(matrix.record_names),
        )

    # --- Publication (R2) --------------------------------------------------

    def publish(self, *, single: bool = True) -> PublishResult:
        """Compile a consolidated Markdown publication and return it (R2).

        Orchestrates ``build_block_tree -> render_block_tree`` for the
        all-records single-file case (mirrors ``publish --all --single``),
        reusing the shared config under ``self._lock`` (E1) — the read cache is
        touched via :meth:`_load` for consistency with the other facade methods.
        Returns the Markdown plus counts of the artifact and text blocks that
        were compiled. Phase A is Markdown-only: no Pandoc/DOCX/PDF and no
        image-manifest side effects. ``FatalError``/``RMSException`` propagate.
        """
        from syntagmax.blocks import ArtifactBlock, TextBlock
        from syntagmax.publish import build_block_tree, render_block_tree

        # Touch the read cache under the lock so publish honours the same
        # single-flight discipline as the other methods (E1).
        self._load()

        tree, _errors = build_block_tree(self._config)
        markdown, _manifest = render_block_tree(tree, self._config, multi_record=not single)

        artifact_count = 0
        text_block_count = 0
        for input_block in tree.inputs:
            for file_record in input_block.files:
                for block in file_record.blocks:
                    if isinstance(block, ArtifactBlock):
                        artifact_count += 1
                    elif isinstance(block, TextBlock):
                        text_block_count += 1

        return PublishResult(
            markdown=markdown,
            artifact_count=artifact_count,
            text_block_count=text_block_count,
        )

    # --- Write seam (R1.7 / R3) -------------------------------------------

    def _extractor_for_record(self, record: InputRecord) -> Extractor:
        """Instantiate the driver's extractor for an input record."""
        return EXTRACTORS[record.driver](self._config, record, self._config.metamodel)

    def _resolve_artifact(self, aid: str) -> Artifact:
        """Return the internal :class:`Artifact` for ``aid`` or raise."""
        artifacts = self._load()
        artifact = artifacts.get(aid)
        if artifact is None:
            raise KeyError(f'No such artifact: {aid}')
        return artifact

    def _extractor_for_artifact(self, artifact: Artifact) -> Extractor:
        if artifact.record is None:
            raise ValueError(f'Artifact "{artifact.aid}" has no input record; cannot resolve a write driver')
        return self._extractor_for_record(artifact.record)

    def edit(
        self,
        aid: str,
        *,
        fields: dict[str, str | None] | None = None,
        body: str | None = None,
    ) -> ArtifactView:
        """Edit an artifact's fields and/or body, returning the fresh view (P1).

        Resolves the artifact's record/driver, calls the R3 write seam,
        reloads the cache, and returns the updated :class:`ArtifactView` so the
        host can refresh its UI without a second :meth:`get` call.
        """
        artifact = self._resolve_artifact(aid)
        extractor = self._extractor_for_artifact(artifact)
        extractor.edit_artifact(artifact, fields=fields, body=body)
        self.reload()
        view = self.get(aid)
        if view is None:  # pragma: no cover - edit must not drop the artifact
            raise RuntimeError(f'Artifact "{aid}" disappeared after edit')
        return view

    def create(
        self,
        *,
        driver_or_record: str | InputRecord,
        target_file: str,
        atype: str,
        aid: str,
        fields: dict | None = None,
        body: str = '',
    ) -> ArtifactView:
        """Create a new artifact and return the created view (R1.7, P1).

        Resolves the extractor from ``driver_or_record``, calls the R3 create
        seam, reloads the cache, and returns the fresh :class:`ArtifactView`.
        """
        record = self._resolve_record(driver_or_record)
        extractor = self._extractor_for_record(record)
        extractor.create_artifact(
            target_file=target_file,
            atype=atype,
            aid=aid,
            fields=fields or {},
            body=body,
        )
        self.reload()
        view = self.get(aid)
        if view is None:  # pragma: no cover - create must yield a visible artifact
            raise RuntimeError(f'Created artifact "{aid}" not found after reload')
        return view

    def delete(self, aid: str) -> None:
        """Delete an artifact and reload the cache (R1.7)."""
        artifact = self._resolve_artifact(aid)
        extractor = self._extractor_for_artifact(artifact)
        extractor.delete_artifact(artifact)
        self.reload()

    # --- Capability introspection (R1.7 / E3) ------------------------------

    def _resolve_record(self, driver_or_record: str | InputRecord) -> InputRecord:
        """Resolve a driver name or :class:`InputRecord` to an ``InputRecord``.

        A string is treated as a driver name; the first matching configured
        input record is returned. When no record uses that driver, a synthetic
        record carrying only the driver name is fabricated (enough for the
        extractor factory and capability introspection).
        """
        if isinstance(driver_or_record, InputRecord):
            return driver_or_record
        for record in self._config.input_records():
            if record.driver == driver_or_record:
                return record
        return InputRecord(
            name=driver_or_record,
            dir='',
            record_base=Path(self._config.root_dir()),
            filepaths=[],
            driver=driver_or_record,
            default_atype='',
            marker='',
        )

    def capabilities(self, driver_or_record: str | InputRecord) -> set[str]:
        """Return the write capabilities for a driver or record (E3, R1.7).

        Reads the extractor's ``WRITE_CAPABILITIES`` set; drivers that do not
        opt in report an empty set.
        """
        record = self._resolve_record(driver_or_record)
        extractor_cls = EXTRACTORS[record.driver]
        return set(extractor_cls.WRITE_CAPABILITIES)
