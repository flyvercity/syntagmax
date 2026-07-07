# Bug Hunter Report — Syntagmax RMS

**Scan date:** 2026-07-07  
**Scan ID:** scan-2026-07-07-150627  
**Tool:** Bug Hunter v3.0.0 (local-sequential pipeline)

---

## 1. Scan Metadata

| Field | Value |
|-------|-------|
| Mode | Extended (local-sequential, single-pass) |
| Target | Full project (`C:\Users\boris\projects\flyvercity\stmx-ws\stmx`) |
| Files scanned | 52 source files |
| Files filtered | 38 (tests/context-only) |
| Architecture | Python RMS with AI analysis, MCP server, VSCode extension, DOORS export plugin |
| Tech stack | Python (Click, FastMCP, Pydantic, GitPython, Polars, Lark), TypeScript (VSCode) |
| Threat model | Not loaded |

## 2. Pipeline Summary

```
Triage:    90 total files | FILE_BUDGET: 60 | Strategy: extended
Recon:     mapped 52 files -> CRITICAL: 0 | HIGH: 0 | MEDIUM: 52 | Tests: 36
Hunters:   deep scan findings: 6
Skeptics:  challenged 6 | disproved: 2, accepted: 4
Referee:   confirmed 4 real bugs -> Critical: 0 | Medium: 4 | Low: 0
```

## 3. Confirmed Bugs

| ID | Severity | Category | File | Claim |
|----|----------|----------|------|-------|
| BUG-1 | Medium | logic | `edit.py:78-85` | NameError: undefined variable `driver` in else branch when `artifact.record` is None |
| BUG-2 | Medium | logic | `metrics.py:28-35` | TBD detection fails for list-valued fields — uses element membership instead of substring matching |
| BUG-3 | Medium | security | `ai_providers.py:237-250` | Gemini API key leaks into error messages via requests exception strings containing the full URL |
| BUG-4 | Medium | logic | `extractors/markdown.py:461-470` | Parser misparses requirements containing literal ` ```yaml ` in content text |

---

### BUG-1: NameError in renumber_artifacts ✅ FIXED

**Severity:** Medium  
**Category:** Logic  
**File:** `syntagmax/src/syntagmax/edit.py` lines 78–85  
**Confidence:** 95% (high)  
**Status:** ✅ FIXED (2026-07-07)  

**Description:**  
In the `renumber_artifacts` function, the variable `driver` is defined only inside the `if record:` block (line 100: `driver = record.driver`). The `else` branch on line 107–108 references `driver` which has never been assigned in that scope, causing a `NameError` at runtime.

**Code:**
```python
for loc_file, updates in updates_by_file.items():
    record = updates[0][0].record
    if record:
        driver = record.driver
        extractor = EXTRACTORS[driver](config, record, config.metamodel)
        if hasattr(extractor, 'update_artifacts'):
            extractor.update_artifacts(loc_file, updates)
        else:
            lg.warning(f'Driver {driver} does not support renumbering yet')
    else:
        lg.error(f'Could not find input record for driver {driver}')  # ← NameError
```

**Runtime trigger:**  
Call `renumber_artifacts` on a project where any artifact has `.record = None`. The code enters the else branch and crashes with `NameError: name 'driver' is not defined`.

**Suggested fix:**  
Replace line 108:
```python
lg.error(f'Could not find input record for artifact at {loc_file}')
```

---

### BUG-2: TBD Detection Fails for List-Valued Fields

**Severity:** Medium  
**Category:** Logic  
**File:** `syntagmax/src/syntagmax/metrics.py` lines 28–35  
**Confidence:** 85% (high)  
**Auto-fix eligibility:** ELIGIBLE  

**Description:**  
The metrics calculation uses `any(config.metrics.tbd_marker in field for field in artifact.fields.values())` to detect TBD markers. Python's `in` operator behaves differently depending on the operand type:

- When `field` is a `str`: `'TBD' in 'some TBD text'` → `True` (substring check ✓)
- When `field` is a `list`: `'TBD' in ['TBD: define later']` → `False` (element membership, NOT substring ✗)

Since `ArtifactBuilder` stores multiple-valued attributes as lists (`artifact.py:119-130`), TBD detection is semantically inconsistent. String fields use substring matching, but list fields use exact element matching.

**Code:**
```python
'has_tbd': any(config.metrics.tbd_marker in field for field in artifact.fields.values()),
```

**Runtime trigger:**  
An artifact has a multiple-valued attribute (e.g., `references = ['REQ-TBD-001', 'item2']`) where an element CONTAINS 'TBD' as a substring but is not exactly equal to 'TBD'. The metrics report will NOT flag this artifact, producing inaccurate TBD percentages.

**Suggested fix:**
```python
def _contains_tbd(marker, value):
    if isinstance(value, list):
        return any(marker in str(item) for item in value)
    return marker in str(value)

# In DataFrame construction:
'has_tbd': any(_contains_tbd(config.metrics.tbd_marker, field) for field in artifact.fields.values()),
```

---

### BUG-3: Gemini API Key Disclosure in Error Messages

**Severity:** Medium  
**Category:** Security (CWE-200: Sensitive Data Exposure)  
**STRIDE:** Information Disclosure  
**File:** `syntagmax/src/syntagmax/ai_providers.py` lines 237–250  
**Confidence:** 80% (high)  
**Auto-fix eligibility:** ELIGIBLE  

**Description:**  
The `GeminiProvider` embeds the API key directly in the URL as a query parameter:
```python
url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
```

When the requests library encounters a connection error (DNS failure, timeout, network error), it includes the full URL in the exception message. The exception handler wraps this with an f-string:
```python
raise AIError(f'Failed to call Gemini: {e}') from e
```

This propagates the API key into the `AIError` message, which is appended to the errors list in `ai.py:67-68` and may surface in report output or log files.

Note: The `_redact_sensitive_info` method exists and correctly handles URL query params (`re.sub(r'([?&]key=)[^&]+', r'\1***REDACTED***', data)`), but it is only called in `lg.debug()` statements, NOT in the exception path.

**Reachability:** INTERNAL (requires Gemini provider configured + network failure)  
**Exploitability:** HARD (requires access to logs/output during a network failure)  

**Runtime trigger:**  
Configure Gemini as the AI provider. The Gemini API endpoint becomes unreachable (DNS failure, firewall, timeout). The `requests.post()` raises a `ConnectionError` whose message includes the full URL with the API key. This propagates through `AIError` → `errors.append()` → potentially into the report.

**Suggested fix (option A — redact in exception):**
```python
except Exception as e:
    redacted_url = self._redact_sensitive_info(url)
    raise AIError(f'Failed to call Gemini at {redacted_url}: {type(e).__name__}') from e
```

**Suggested fix (option B — use header instead of URL param):**
```python
url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
resp = requests.post(url, json=body, headers=headers, timeout=timeout_s)
```

---

### BUG-4: Markdown Parser Boundary Detection Flaw

**Severity:** Medium  
**Category:** Logic  
**File:** `syntagmax/src/syntagmax/extractors/markdown.py` lines 461–470  
**Confidence:** 76% (medium)  
**Auto-fix eligibility:** ELIGIBLE  

**Description:**  
The markdown parser's segment boundary detection uses:
```python
yaml_start_pos = markdown.find('```yaml', start_pos)
```

This searches the ENTIRE remaining document from the requirement's opening marker position forward, without constraining the search to within the current requirement's scope. If the requirement's content text contains the literal string ` ```yaml ` (e.g., a requirement documenting a YAML format), this is incorrectly identified as the metadata boundary.

**Consequences:**
1. The requirement segment is truncated at the content's literal ` ```yaml `, losing everything after it
2. The truncated or malformed segment either fails Lark parsing (producing an `ErrorBlock`) or parses incorrectly
3. Valid requirements are rejected or corrupted

**Code:**
```python
# Find segment end
yaml_start_pos = markdown.find('```yaml', start_pos)  # ← Global search, not scoped
slash_req_match = re.search(rf'\[/{marker}\]', markdown[start_pos:], re.IGNORECASE)
slash_req_pos = (start_pos + slash_req_match.start()) if slash_req_match else -1

if yaml_start_pos != -1 and (slash_req_pos == -1 or yaml_start_pos < slash_req_pos):
    end_pos = markdown.find('```', yaml_start_pos + 7)
    if end_pos != -1:
        segment_end = end_pos + 3
```

**Runtime trigger:**  
A markdown file containing a requirement whose content documents YAML syntax:
```markdown
[REQ]
This configuration uses the following format:
```yaml
key: value
nested:
  item: data
```
[id] REQ-001
```yaml
attrs:
  status: Draft
```
```

The parser identifies the first ` ```yaml ` (inside the content) as the metadata boundary instead of the actual metadata block.

**Suggested fix:**
```python
# Find [/MARKER] first to establish the outer boundary
slash_req_match = re.search(rf'\[/{marker}\]', markdown[start_pos:], re.IGNORECASE)
slash_req_pos = (start_pos + slash_req_match.start()) if slash_req_match else -1
max_boundary = slash_req_pos if slash_req_pos != -1 else len(markdown)

# Search for ```yaml only within the bounded region
yaml_start_pos = markdown.find('```yaml', start_pos, max_boundary)
```

---

## 4. Low-Confidence Items

None — all confirmed bugs have confidence ≥ 76%.

## 5. Dismissed Findings

<details>
<summary>2 dismissed findings (click to expand)</summary>

| ID | Severity | File | Claim | Dismissal Reason |
|----|----------|------|-------|------------------|
| BUG-5 | Low | `tree.py:114-117` | Circular reference detection breaks out of ancestor propagation loop early, leaving remaining nodes with incomplete ancestor sets | The `ansestors` field is never consumed by any downstream code — dead data with zero observable impact |
| BUG-6 | Low | `doors-export/__init__.py:16` | Dead sanitization regex `_SANITIZE_RE` never applied to output paths | Factually wrong — `_SANITIZE_RE` IS actively used by `_sanitize_filename()` (line 102/113) |

</details>

## 6. Agent Accuracy Stats

| Metric | Value |
|--------|-------|
| Deep Hunter accuracy | 4/6 confirmed (67%) |
| Skeptic accuracy | 2/2 correct challenges (100%) |
| False positive rate | 33% (2/6 findings disproved) |

## 7. Coverage Assessment

✅ **Full queued coverage achieved.**

All 52 scannable source files were read directly during the scan. No files were skipped.

| Domain | Files | Coverage |
|--------|-------|----------|
| syntagmax (core library) | 38/38 | 100% |
| syntagmax-doors-export-plugin | 10/10 | 100% |
| syntagmax-vscode | 4/4 | 100% |

---

## Summary

| Metric | Count |
|--------|-------|
| Total findings reported | 6 |
| Confirmed bugs | 4 |
| Dismissed | 2 |
| By severity | Critical: 0, High: 0, Medium: 4, Low: 0 |
| By category | Security: 1, Logic: 3 |
| Auto-fix eligible | 4/4 |
