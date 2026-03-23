## 2025-04-07 - Cached ID Schema Regexes in ArtifactValidator
**Learning:** The `_validate_id_schema` method was previously recompiling the `{num}` extraction regex for every artifact, and dynamically building and compiling the final schema pattern on every call.
**Action:** When working with systems that validate large numbers of items against string-interpolated schemas (like custom DSLs or artifact systems), always consider hoisting static regex compilations and caching the final compiled patterns keyed by the dynamic input (e.g. `(schema, artifact_type)`).
