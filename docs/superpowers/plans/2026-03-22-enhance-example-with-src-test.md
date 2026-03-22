# Enhance Example with Mock Source Code and Tests Implementation Plan (Corrected)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the `obsidian-driver` example by adding `SRC` and `TEST` artifacts with correct `text` driver syntax and lowercase attributes.

**Architecture:** 
1. Update `text.lark` to support lowercase `id=` and `type=`.
2. Update the metamodel with `SRC` and `TEST` types.
3. Update `config.toml` with new inputs.
4. Create mock artifacts using the syntax: `[< id=... type=... parent=... >>> code >]`.

**Tech Stack:** Syntagmax (Python), Lark (Grammar), TOML (Config)

---

### Task 0: Update Text Extractor Grammar

**Files:**
- Modify: `src/syntagmax/extractors/text.lark`

- [ ] **Step 1: Allow lowercase 'id' and 'type' in directives**

```lark
// src/syntagmax/extractors/text.lark
directive: id_directive | type_directive | attr_directive

id_directive: ("ID" | "id") "=" AID
type_directive: ("TYPE" | "type") "=" ATYPE
attr_directive: NAME "=" VALUE
```

- [ ] **Step 2: Commit**

```bash
git add src/syntagmax/extractors/text.lark
git commit -m "feat: support lowercase id and type in text extractor"
```

### Task 1: Update Metamodel

**Files:**
- Modify: `example/obsidian-driver/.syntagmax/project.syntagmax`

- [ ] **Step 1: Add SRC and TEST artifact definitions and trace rules**

```text
# ... (existing definitions)

# Source code
artifact SRC:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute parent is mandatory reference to parent

# Tests
artifact TEST:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute parent is mandatory multiple reference to parent

trace from REQ to SYS is mandatory
trace from SRC to REQ is mandatory
trace from TEST to REQ or SRC is mandatory
```

- [ ] **Step 2: Commit**

```bash
git add example/obsidian-driver/.syntagmax/project.syntagmax
git commit -m "example: add SRC and TEST to metamodel"
```

### Task 2: Update Configuration

**Files:**
- Modify: `example/obsidian-driver/.syntagmax/config.toml`

- [ ] **Step 1: Add new input records for implementation and verification**

```toml
[[input]]
name = "implementation"
dir = "src"
driver = "text"
atype = "SRC"

[[input]]
name = "verification"
dir = "tests"
driver = "text"
atype = "TEST"
```

- [ ] **Step 2: Commit**

```bash
git add example/obsidian-driver/.syntagmax/config.toml
git commit -m "example: add implementation and verification inputs to config"
```

### Task 3: Create Mock Source Code (SRC)

**Files:**
- Create: `example/obsidian-driver/src/telemetry.py`
- Create: `example/obsidian-driver/src/failsafe.py`
- Create: `example/obsidian-driver/src/mavlink.py`
- Create: `example/obsidian-driver/src/contingency.py`

- [ ] **Step 1: Create `example/obsidian-driver/src/telemetry.py`**

```python
# [< id=SRC-001 type=SRC parent=REQ-001 >>>
class TelemetryPipeline:
    def __init__(self, rate_hz=10):
        self.rate_hz = rate_hz

    def push(self, data):
        # Non-blocking push to queue
        pass
# >]
```

- [ ] **Step 2: Create `example/obsidian-driver/src/failsafe.py`**

```python
# [< id=SRC-002 type=SRC parent=REQ-002 >>>
def handle_failsafe(event):
    if event == 'LINK_LOSS':
        trigger_rth()
# >]
```

- [ ] **Step 3: Create `example/obsidian-driver/src/mavlink.py`**

```python
# [< id=SRC-003 type=SRC parent=REQ-003 >>>
class MAVLinkManager:
    def connect(self, uri):
        # Establish encrypted session
        pass
# >]
```

- [ ] **Step 4: Create `example/obsidian-driver/src/contingency.py`**

```python
# [< id=SRC-004 type=SRC parent=REQ-004 >>>
def activate_contingency_mode():
    # Transfer control to GCS
    pass
# >]
```

- [ ] **Step 5: Commit**

```bash
git add example/obsidian-driver/src/*.py
git commit -m "example: add mock source code artifacts"
```

### Task 4: Create Mock Tests (TEST)

**Files:**
- Create: `example/obsidian-driver/tests/test_telemetry.py`
- Create: `example/obsidian-driver/tests/test_failsafe.py`
- Create: `example/obsidian-driver/tests/test_mavlink.py`
- Create: `example/obsidian-driver/tests/test_contingency.py`

- [ ] **Step 1: Create `example/obsidian-driver/tests/test_telemetry.py`**

```python
# [< id=TEST-001 type=TEST parent=REQ-001 parent=SRC-001 >>>
def test_telemetry_rate_10hz():
    pipe = TelemetryPipeline(rate_hz=10)
    assert pipe.rate_hz == 10
# >]
```

- [ ] **Step 2: Create `example/obsidian-driver/tests/test_failsafe.py`**

```python
# [< id=TEST-002 type=TEST parent=REQ-002 parent=SRC-002 >>>
def test_failsafe_rth_trigger():
    # Simulate link loss and check RTH trigger
    pass
# >]
```

- [ ] **Step 3: Create `example/obsidian-driver/tests/test_mavlink.py`**

```python
# [< id=TEST-003 type=TEST parent=REQ-003 parent=SRC-003 >>>
def test_mavlink_reconnection():
    # Test graceful reconnection after link drop
    pass
# >]
```

- [ ] **Step 4: Create `example/obsidian-driver/tests/test_contingency.py`**

```python
# [< id=TEST-004 type=TEST parent=REQ-004 parent=SRC-004 >>>
def test_gcs_takeover():
    # Verify manual control takeover
    pass
# >]
```

- [ ] **Step 5: Commit**

```bash
git add example/obsidian-driver/tests/*.py
git commit -m "example: add mock test artifacts"
```

### Task 5: Final Verification

**Files:**
- Run commands in terminal

- [ ] **Step 1: Run extraction and analysis**

Run: `uv run python -m syntagmax.main extract -c example/obsidian-driver/.syntagmax/config.toml`
Run: `uv run python -m syntagmax.main analyse -c example/obsidian-driver/.syntagmax/config.toml`

Expected: No errors, all 16 artifacts extracted (4 SYS, 4 REQ, 4 SRC, 4 TEST).

- [ ] **Step 2: Inspect outputs**

Check `example/obsidian-driver/output/impact.md` and `example/obsidian-driver/output/metrics.md`.
Verify they include the new SRC and TEST artifacts.
