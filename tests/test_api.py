# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2026-09-28
# Description: Tests for the syntagmax.api embedding facade (read side).

import shutil
import threading
from pathlib import Path

import pytest

from syntagmax import api
from syntagmax.config import Config, Params
from syntagmax.errors import FatalError, UnsupportedOperation


# The obsidian-driver example is the richest read fixture: multiple artifact
# types (SYS, REQ, SRC, TEST), parent/child links, and body contents.
EXAMPLE_CONFIG = Path(__file__).parents[1] / 'example' / 'obsidian-driver' / '.syntagmax' / 'config.toml'
EXAMPLE_PROJECT = EXAMPLE_CONFIG.parents[1]


def _cli_style_config() -> Config:
    """Build a Config the way the CLI ``analyze`` command does, for parity."""
    params = Params(
        render_tree=False,
        ai=False,
        cwd=str(EXAMPLE_CONFIG.parent),
        no_git=True,
        allow_dirty_worktree=False,
        language='en',
        suppress_tracing=False,
        tasks=False,
    )
    return Config(params, EXAMPLE_CONFIG)


def _facade_session() -> api.Session:
    return api.open_project(EXAMPLE_CONFIG, options=api.Options(no_git=True))


# --- Options -> Params translation ---


def test_options_to_params_defaults():
    params = api._options_to_params(api.Options(), cwd='/tmp/x')
    assert params['render_tree'] is False
    assert params['ai'] is False
    assert params['cwd'] == '/tmp/x'
    assert params['no_git'] is False
    assert params['allow_dirty_worktree'] is False
    assert params['language'] == 'en'
    assert params['suppress_tracing'] is False
    assert params['tasks'] is False
    assert params['warnings_as_errors'] is False
    # log_level defaults to None -> omitted (NotRequired)
    assert 'log_level' not in params


def test_options_to_params_log_level_included():
    params = api._options_to_params(api.Options(log_level='debug'), cwd='/x')
    assert params['log_level'] == 'debug'


# --- Config parity ---


def test_config_parity_root_output_input():
    cli_config = _cli_style_config()
    session = _facade_session()
    facade_config = session._config

    assert facade_config.root_dir() == cli_config.root_dir()
    assert facade_config.output_dir() == cli_config.output_dir()

    facade_records = {r.name: r for r in facade_config.input_records()}
    cli_records = {r.name: r for r in cli_config.input_records()}
    assert facade_records.keys() == cli_records.keys()
    for name, facade_rec in facade_records.items():
        cli_rec = cli_records[name]
        assert facade_rec.dir == cli_rec.dir
        assert facade_rec.driver == cli_rec.driver
        assert facade_rec.default_atype == cli_rec.default_atype
        assert facade_rec.record_base == cli_rec.record_base
        assert sorted(facade_rec.filepaths) == sorted(cli_rec.filepaths)


# --- get / query / search ---


def test_get_returns_view_with_parents():
    session = _facade_session()

    req = session.get('REQ-001')
    assert req is not None
    assert req.aid == 'REQ-001'
    assert req.atype == 'REQ'
    # REQ-001 declares [parent] SYS-001
    parent_pids = {p['pid'] for p in req.parents}
    assert 'SYS-001' in parent_pids
    for p in req.parents:
        assert set(p.keys()) == {'pid', 'nominal_revision', 'is_suspicious'}

    # No git in the pipeline sequence -> no revisions populated.
    assert req.latest_revision is None


def test_get_missing_returns_none():
    session = _facade_session()
    assert session.get('DOES-NOT-EXIST') is None


def test_view_fields_do_not_alias_cached_artifact():
    """Mutating a returned view's fields must not corrupt the cached artifact.

    Regression for the aliasing finding: ``_to_view`` previously handed out the
    artifact's own ``fields`` dict (and its nested list values) by reference, so
    a host mutating ``session.get(aid).fields`` changed the in-memory cache and
    later reads reported data absent from the source document.
    """
    session = _facade_session()

    view = session.get('REQ-001')
    assert view is not None

    # Mutate the top-level mapping and any nested list values in place.
    view.fields['status'] = 'MUTATED-BY-HOST'
    view.fields['injected'] = 'ghost'
    for value in view.fields.values():
        if isinstance(value, list):
            value.append('MUTATED-LIST-ENTRY')

    # A fresh view (from the same cached artifact) must be untouched.
    refetched = session.get('REQ-001')
    assert refetched is not None
    assert refetched.fields.get('status') == 'active'
    assert 'injected' not in refetched.fields
    for value in refetched.fields.values():
        if isinstance(value, list):
            assert 'MUTATED-LIST-ENTRY' not in value


def test_children_populated():
    session = _facade_session()
    sys1 = session.get('SYS-001')
    assert sys1 is not None
    # REQ-001 has parent SYS-001, so SYS-001 must list REQ-001 as a child.
    assert 'REQ-001' in sys1.children


def test_query_all_excludes_root():
    session = _facade_session()
    views = session.query()
    atypes = {v.atype for v in views}
    assert 'ROOT' not in atypes
    assert 'REQ' in atypes
    assert 'SYS' in atypes


def test_query_filters_by_atype():
    session = _facade_session()
    reqs = session.query(atype='REQ')
    assert reqs, 'expected at least one REQ artifact'
    assert all(v.atype == 'REQ' for v in reqs)
    aids = {v.aid for v in reqs}
    assert 'REQ-001' in aids
    assert 'SYS-001' not in aids


def test_search_matches_aid():
    session = _facade_session()
    results = session.search('REQ-001')
    assert any(v.aid == 'REQ-001' for v in results)


def test_search_matches_atype():
    session = _facade_session()
    results = session.search('SYS')
    assert results
    assert all('sys' in (v.aid + v.atype + str(v.fields)).lower() for v in results)


def test_search_matches_body_contents():
    # REQ-001's marked body/contents contains "serializes" and "non-blocking",
    # which appear in no aid/atype/title — only in the extracted contents text.
    session = _facade_session()
    results = session.search('serializes')
    aids = {v.aid for v in results}
    assert 'REQ-001' in aids


def test_search_multi_term_and_semantics():
    session = _facade_session()
    # Both terms co-occur only within REQ-001's contents body.
    both = session.search('non-blocking serializes')
    assert 'REQ-001' in {v.aid for v in both}

    # A term that does not co-occur with 'serializes' anywhere excludes all matches.
    none = session.search('serializes zzzznonexistentterm')
    assert none == []


def test_search_case_insensitive():
    session = _facade_session()
    lower = {v.aid for v in session.search('telemetry')}
    upper = {v.aid for v in session.search('TELEMETRY')}
    assert lower == upper
    assert lower  # non-empty


# --- Concurrency smoke test ---


def test_concurrent_artifacts_and_reload():
    session = _facade_session()
    errors: list[Exception] = []

    def worker_read():
        try:
            for _ in range(20):
                result = session.artifacts()
                assert 'REQ-001' in result
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    def worker_reload():
        try:
            for _ in range(20):
                session.reload()
                session.artifacts()
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=worker_read), threading.Thread(target=worker_reload)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f'threads raised: {errors}'
    # Cache remains coherent after concurrent access.
    assert 'REQ-001' in session.artifacts()


# --- Fatal error propagation ---


def test_fatal_error_on_broken_config_path():
    broken = Path(__file__).parents[1] / 'example' / 'nonexistent-project' / '.syntagmax' / 'config.toml'
    with pytest.raises(FatalError):
        api.open_project(broken)


# --- analyse() (R1.6, X1 mapping) ---


def _copy_example_project(tmp_path: Path) -> Path:
    """Copy the obsidian-driver example into ``tmp_path`` so tests can mutate
    it freely without touching the repository fixture. Returns the config path.
    """
    dest = tmp_path / 'obsidian-driver'
    shutil.copytree(EXAMPLE_PROJECT, dest)
    return dest / '.syntagmax' / 'config.toml'


def test_analyse_maps_report_error_to_diagnostic(tmp_path):
    # Introduce a known schema violation: REQ-099 with an invalid `priority`
    # enum value. The attribute validator produces a ReportError carrying
    # artifact_id, file_path, and line_range — exercising the full X1 mapping.
    config_path = _copy_example_project(tmp_path)
    bad = config_path.parents[1] / 'REQ' / 'REQ-099.md'
    bad.write_text(
        '# REQ-099: Bad Priority\n\n'
        '[REQ]\n'
        'A requirement with an invalid priority value.\n'
        '[id] REQ-099\n'
        '[parent] SYS-001\n'
        '```yaml\n'
        'attrs:\n'
        '  title: Bad Priority Req\n'
        '  status: active\n'
        '  priority: bogus\n'
        '  derived: false\n'
        '```\n',
        encoding='utf-8',
    )

    session = api.open_project(config_path, options=api.Options(no_git=True))
    result = session.analyse()

    assert isinstance(result, api.AnalysisResult)
    # metrics pass through from the core Report (benedict); impact is None
    # here because populate_revisions/impact are skipped with no_git.
    assert result.metrics is not None

    diags = [d for d in result.diagnostics if d.artifact_id == 'REQ-099']
    assert diags, f'expected a diagnostic for REQ-099, got: {result.diagnostics}'
    diag = diags[0]

    assert diag.severity == 'error'
    assert diag.artifact_id == 'REQ-099'
    assert diag.category == 'attribute'
    # rule falls back to category when the source error has no explicit rule.
    assert diag.rule == 'attribute'
    # location combines file_path and line_range: 'REQ/REQ-099.md:3-13'.
    assert diag.location.startswith('REQ/REQ-099.md:')
    assert ':' in diag.location and '-' in diag.location.split(':', 1)[1]
    assert 'priority' in diag.message


def test_analyse_diagnostic_location_falls_back_to_file_path():
    """The X1 mapping uses ``file_path`` alone when ``line_range`` is absent.

    The error-handling example emits extraction errors that carry neither an
    artifact_id nor a line_range, so ``location`` degrades to an empty string
    (``e.file_path or ''`` with no file_path) and ``rule`` falls back to the
    category. This locks in the else-branch of the mapping.
    """
    config = Path(__file__).parents[1] / 'example' / 'error-handling' / '.syntagmax' / 'config.toml'
    session = api.open_project(config, options=api.Options(no_git=True))
    result = session.analyse()

    assert result.diagnostics, 'error-handling example should surface diagnostics'
    for diag in result.diagnostics:
        # Extraction errors have no explicit rule -> falls back to category.
        assert diag.rule == diag.category
        # No line_range and no file_path on these -> empty location string.
        assert diag.location == ''


# --- edit() / delete() / capabilities() (R1.7, R3, P1) ---


def test_edit_obsidian_returns_updated_view(tmp_path):
    config_path = _copy_example_project(tmp_path)
    session = api.open_project(config_path, options=api.Options(no_git=True))

    before = session.get('REQ-001')
    assert before is not None
    assert before.fields.get('status') == 'active'

    # edit() must RETURN the updated view (P1) — no separate get() needed.
    updated = session.edit('REQ-001', fields={'status': 'retired'})
    assert isinstance(updated, api.ArtifactView)
    assert updated.aid == 'REQ-001'
    assert updated.fields.get('status') == 'retired'

    # And the change is durable across a fresh get().
    refetched = session.get('REQ-001')
    assert refetched is not None
    assert refetched.fields.get('status') == 'retired'


def test_edit_obsidian_replaces_body(tmp_path):
    config_path = _copy_example_project(tmp_path)
    session = api.open_project(config_path, options=api.Options(no_git=True))

    new_body = 'The flight computer shall do something entirely new and testable.'
    updated = session.edit('REQ-001', body=new_body)
    assert new_body in str(updated.fields.get('contents'))


def test_edit_non_obsidian_raises_unsupported(tmp_path):
    # SRC-001 uses the 'text' driver, which does not implement the write seam.
    config_path = _copy_example_project(tmp_path)
    session = api.open_project(config_path, options=api.Options(no_git=True))

    assert session.get('SRC-001') is not None
    with pytest.raises(UnsupportedOperation):
        session.edit('SRC-001', fields={'status': 'active'})


def test_delete_obsidian_removes_artifact(tmp_path):
    config_path = _copy_example_project(tmp_path)
    session = api.open_project(config_path, options=api.Options(no_git=True))

    # REQ-005 lives alone in REQ/REQ-005.md; deleting it removes the file.
    req_file = config_path.parents[1] / 'REQ' / 'REQ-005.md'
    assert req_file.exists()
    assert session.get('REQ-005') is not None

    result = session.delete('REQ-005')
    assert result is None
    # The write seam removed the underlying file (it was the sole artifact).
    assert not req_file.exists()


def test_capabilities_obsidian_and_non_obsidian():
    session = _facade_session()

    # Obsidian opts into the full write seam.
    assert session.capabilities('obsidian') == {'edit', 'create', 'delete'}

    # The 'text' driver does not opt in -> empty capability set.
    assert session.capabilities('text') == set()


def test_capabilities_accepts_input_record(tmp_path):
    config_path = _copy_example_project(tmp_path)
    session = api.open_project(config_path, options=api.Options(no_git=True))

    records = {r.driver: r for r in session._config.input_records()}
    assert session.capabilities(records['obsidian']) == {'edit', 'create', 'delete'}
    assert session.capabilities(records['text']) == set()
