# Design: Enhancing the Example with Mock Source Code and Tests

## 1. Overview
The goal is to enhance the `obsidian-driver` example in `example/obsidian-driver/` by adding mock source code and test artifacts. This demonstrates the full traceability lifecycle from system requirements (SYS) to software requirements (REQ) to implementation (SRC) and verification (TEST).

## 2. Metamodel Changes
The metamodel in `example/obsidian-driver/.syntagmax/project.syntagmax` will be updated to include two new artifact types: `SRC` and `TEST`.

### 2.1 Artifact: SRC
Represents a source code unit.
- **Attributes**:
    - `id`: mandatory string
    - `contents`: mandatory string (the code itself)
    - `parent`: mandatory reference to parent (`REQ`)
- **Trace Rules**:
    - Mandatory trace from `SRC` to `REQ`.

### 2.2 Artifact: TEST
Represents a test case.
- **Attributes**:
    - `id`: mandatory string
    - `contents`: mandatory string (the test code)
    - `parent`: mandatory multiple reference to parent (`REQ` or `SRC`)
- **Trace Rules**:
    - Mandatory trace from `TEST` to `REQ` or `SRC`.

## 3. Configuration Changes
The project configuration in `example/obsidian-driver/.syntagmax/config.toml` will be updated to include the new artifact sources.

### 3.1 New Input Records
- **Implementation**:
    - `name`: "implementation"
    - `dir`: "src"
    - `driver`: "text"
    - `atype`: "SRC"
- **Verification**:
    - `name`: "verification"
    - `dir`: "tests"
    - `driver`: "text"
    - `atype`: "TEST"

## 4. Implementation Details
The `text` extractor will be used for both `SRC` and `TEST` artifacts. It expects metadata markers like `[< ID=... TYPE=... >]` and the body content following `>>>`.

### 4.1 Example Mock Artifacts
Mock files will be created in `example/obsidian-driver/src/` and `example/obsidian-driver/tests/`.

#### 4.1.1 SRC Examples:
- `src/telemetry.py` (SRC-001 -> REQ-001)
- `src/failsafe.py` (SRC-002 -> REQ-002)
- `src/mavlink.py` (SRC-003 -> REQ-003)
- `src/contingency.py` (SRC-004 -> REQ-004)

#### 4.1.2 TEST Examples:
- `tests/test_telemetry.py` (TEST-001 -> REQ-001, SRC-001)
- `tests/test_failsafe.py` (TEST-002 -> REQ-002, SRC-002)
- `tests/test_mavlink.py` (TEST-003 -> REQ-003, SRC-003)
- `tests/test_contingency.py` (TEST-004 -> REQ-004, SRC-004)

## 5. Verification Plan
- Run `syntagmax extract` on the example project.
- Verify that all 16 artifacts (4 SYS, 4 REQ, 4 SRC, 4 TEST) are correctly extracted.
- Run `syntagmax analyse` and ensure no validation errors are present (all mandatory traces and attributes are correct).
- Inspect the generated `output/impact.md` and `output/metrics.md` to ensure they reflect the new artifacts.
