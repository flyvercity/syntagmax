# Critique: Attribute Presence Mode for Publishing

## Executive Summary

The specification [attribute-presence.spec.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/attribute-presence.spec.md) describes a well-designed feature that satisfies user needs for compliance-ready document rendering by controlling how empty/missing attributes are presented. 

However, one high-priority **Must-Address** item has been identified: the proposed default value (`all`) introduces a breaking change for existing installations. Additionally, several **Recommendations** have been made to improve codebase hygiene (avoiding duplication of condition evaluation logic), alignment with configuration conventions (hyphenated aliases), and observability (warnings on silent configuration degradation).

With the updates suggested below, the specification is highly actionable and ready for implementation.

---

## Product Lens Findings

### 1a. Problem Validation & Scope
The problem is well-defined: compliance and audit traceability documents often require all fields (even empty ones) to be explicitly represented to show that they were not overlooked. The scope is appropriate and fits cleanly into the existing publish sections model.

### 1b. User Value Assessment (Severity: 🎯 Must-Address)
* **Finding (P1 - Default Behavior):** The spec proposes that the default value for the global `attribute_presence` setting be `all`. Currently, the publish renderer only outputs attributes with actual values (equivalent to `values-only`). Changing the default to `all` will cause a breaking change for all existing users upon upgrade: their documents will suddenly render empty cells/rows for all missing optional attributes.
* **Suggestion:** Change the default value of global `attribute_presence` to `values-only` to preserve backward compatibility.

### 1d. Edge Cases & UX (Severity: 💡 Recommendation)
* **Finding (P2 - Text Section Ignored Settings):** The spec states in Task 4 that `attribute_presence` will be accepted on `TextSection` for uniformity, but will have no visible effect because empty text sections are always skipped. Accepting a configuration parameter that has no functional effect can confuse users.
* **Suggestion:** Either:
  1. Do not add `attribute_presence` to `TextSection` (it will be rejected due to `extra='forbid'`), OR
  2. Implement placeholder rendering for empty text attributes (e.g., rendering `**Label**: (none)` or `**Label**: N/A`) when `attribute_presence` is set to `all` or `mandatory`.

### 1e. Success Measurement (Severity: 🤔 Question)
* **Finding (P3 - Fallback Renderer Limitation):** The spec notes that the fallback renderer (`render_artifact_fallback`) is unaffected. Users who configure the global `attribute_presence: all` without overriding specific artifact render rules might expect their fallback tables to also display all metamodel attributes.
* **Suggestion:** Clarify if fallback rendering should eventually support this feature, or document this limitation clearly in the user guide.

---

## Engineering Lens Findings

### 2a. Architecture Soundness (Severity: 💡 Recommendation)
* **Finding (E1 - Code Duplication):** Task 2 proposes implementing `_is_anchor_truthy` and `is_attribute_mandatory` within [publish.py](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/src/syntagmax/publish.py). This duplicates the boolean evaluation and metamodel condition resolution logic already present in `ArtifactValidator._evaluate_condition` in [analyse.py](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/src/syntagmax/analyse.py).
* **Suggestion:** Refactor the condition and truthiness evaluation logic into a shared helper function (e.g., in [metamodel.py](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/src/syntagmax/metamodel.py) or a shared helpers module) and reuse it in both the analyzer and the publisher.

### 2b. Failure Mode Analysis (Severity: 💡 Recommendation)
* **Finding (E3 - Metamodel Degradation Observability):** If `mandatory` mode is selected but the metamodel is unavailable (e.g., missing file, config error), the system silently degrades to `values-only` mode. This makes configuration errors hard to troubleshoot.
* **Suggestion:** Add warning logs when `attribute_presence` is set to `mandatory` but `config.metamodel` is `None` or unavailable.

### 2g. Dependencies & Integration (Severity: 💡 Recommendation)
* **Finding (E2 - Missing Configuration Aliases):** The configuration format uses hyphenated names (like `table-spacer` and `docx-template`). Defining `attribute_presence` without a hyphenated alias means configuring `attribute-presence` will fail validation.
* **Suggestion:** Define `attribute_presence` with `alias='attribute-presence'` in Pydantic models:
  ```python
  attribute_presence: AttributePresence = Field(default='values-only', alias='attribute-presence')
  ```

---

## Cross-Lens Insights

* **X1: Default Behavior (🎯 Must-Address):** Standardizing on `values-only` as the default maintains rendering parity for existing users (Product UX) and avoids breaking existing end-to-end markdown snapshot tests (Engineering readiness).

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 | User Value | Defaulting to `all` causes a breaking change in output formatting. | Change default to `values-only`. |
| **P2** | Product | 💡 | Edge Cases & UX | `attribute_presence` on `TextSection` is silently ignored. | Do not add to `TextSection` or support placeholder text. |
| **P3** | Product | 🤔 | UX / Fallback | Fallback renderer does not respect the presence setting. | Clarify fallback renderer scope and document limitation. |
| **E1** | Engineering | 💡 | Architecture | Duplicate condition evaluation logic in `publish.py` and `analyse.py`. | Extract condition evaluation to a shared helper. |
| **E2** | Engineering | 💡 | Integration | Missing hyphenated alias for config keys. | Add `alias='attribute-presence'` to Pydantic models. |
| **E3** | Engineering | 💡 | Observability | Silent degradation to `values-only` when metamodel is missing. | Add warning log when metamodel is missing in `mandatory` mode. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

*All identified issues are readily resolvable. Proceeding to implementation is recommended once the proposed updates are applied.*

---

## Offer Remediation

### Proposed Edits to `docs/specs/attribute-presence.spec.md`

#### Edit 1: Requirements (Default & TextSection)

```diff
-1. Add a global `attribute_presence` setting in the publish config with values: `all`, `mandatory`, `values-only`. Default: `all`.
+1. Add a global `attribute_presence` setting in the publish config with values: `all`, `mandatory`, `values-only`. Default: `values-only` (to preserve backward compatibility).
```

```diff
-16. For text sections: attributes without values are skipped (empty bold label with no text is not useful).
+16. For text sections: attributes without values are skipped (empty bold label with no text is not useful). The `attribute_presence` setting is not supported on `TextSection` to avoid confusion.
```

#### Edit 2: Architecture & Pydantic Config

```diff
-1. Define `AttributePresence = Literal['all', 'mandatory', 'values-only']` type alias.
-2. Add `attribute_presence: AttributePresence` field to `PublishConfig` (default `'all'`).
-3. Add `attribute_presence: AttributePresence | None` field to `TableSection` and `TextSection` (default `None`, meaning "use global").
+1. Define `AttributePresence = Literal['all', 'mandatory', 'values-only']` type alias.
+2. Add `attribute_presence: AttributePresence` field to `PublishConfig` (default `'values-only'`, alias `'attribute-presence'`).
+3. Add `attribute_presence: AttributePresence | None` field to `TableSection` (default `None`, alias `'attribute-presence'`, meaning "use global").
```

#### Edit 3: Shared Condition Evaluator

```diff
-4. Create a helper `is_attribute_mandatory(attr_name, atype, artifact, metamodel) -> bool` that evaluates metamodel rules with conditions.
+4. Extract condition evaluation from `analyse.py` into a shared helper in `metamodel.py`. Define `is_attribute_mandatory(attr_name, atype, artifact, metamodel) -> bool` using this shared helper. Log a warning if mode is `mandatory` but metamodel is unavailable.
```
