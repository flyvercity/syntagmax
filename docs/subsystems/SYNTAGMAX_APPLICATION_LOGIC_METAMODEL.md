# Syntagmax Application Logic — Metamodel Subsystem

> Covers the `.syntagmax` DSL grammar, parsing, normalized model, validation, conditions, booleans, ID schemas, and trace declarations. Source: `metamodel.py`, `metamodel.lark`, `id_utils.py`.

## 1. DSL shape

```text
artifact TYPE:
    id is string [as SCHEMA]
    attribute NAME is mandatory|optional [multiple] TYPE [if [not] BOOLEAN]

trace from SOURCE to TARGET [or TARGET] is mandatory|optional [via commit|timestamp] [if [not] BOOLEAN]
```

Supported attribute types:

- `string`;
- `integer`;
- `boolean`;
- `boolean [true: VALUE, ... , false: VALUE, ...]`;
- `reference`;
- `reference to parent`;
- `enum [VALUE, ...]`.

Identifiers accept letters, digits, underscore, and hyphen after an initial letter.

## 2. Parsing

1. Load package grammar and create an indented LALR Lark parser.
2. Parse model text.
3. Transform artifact rules into dictionaries grouped by artifact name and attribute name.
4. Transform trace rules into a source-type keyed list.
5. Normalize output:

```text
{
  artifacts: {TYPE: {artifact_name, attributes: {name: [rules]}}},
  traces: {SOURCE: [trace_rules]}
}
```

6. Validate unless `validate=False` was requested.
7. Precompute truthy sets for boolean attributes.
8. Any parse/transform/validation error becomes `FatalError` through the caller’s error list.

Multiple rules for one attribute are retained as a list, enabling conditional variants.

## 3. Rule normalization

### Attribute rule

```text
{
  name,
  presence: mandatory|optional,
  multiple: bool,
  type_info,
  condition: {anchor, negated} | None,
  id_rule: false
}
```

### ID rule

`id is TYPE [as SCHEMA]` is normalized as a mandatory, scalar rule named `id` with `id_rule=true` and optional schema.

### Type info

- string: `{type: string}`;
- integer: `{type: integer}`;
- boolean: `{type: boolean}` or custom true/false lists;
- reference: `{type: reference, to_parent: bool}`;
- enum: `{type: enum, allowed: [...]}`.

### Trace rule

```text
{
  type: trace,
  source,
  targets: [...],
  presence: mandatory|optional,
  mode: timestamp|commit,
  condition: ... | None
}
```

Default trace mode is `timestamp`.

## 4. Metamodel validation

For every artifact definition:

1. A regular attribute named `id` is forbidden; use the special `id is ...` rule.
2. Every conditional rule anchor must exist.
3. Every conditional anchor must be a non-conditional boolean rule.
4. At least one non-conditional mandatory ID rule is required.
5. At most one `{num}` macro is allowed in each ID schema.
6. At least one non-conditional mandatory `contents` rule is required.

For traces:

- conditional anchors must exist on the source artifact;
- anchors must be non-conditional booleans;
- unknown source/target type validation is partly delegated to broader model checks.

Any accumulated violation raises `FatalError` when loading with validation enabled.

## 5. Conditions

Condition form: `if anchor` or `if not anchor`.

Evaluation:

- no condition → true;
- missing anchor value → false before negation;
- Python bool → use directly;
- textual value → lower-case membership in custom truthy set or default `{true, yes, 1}`;
- `not` reverses the result.

Only non-conditional boolean anchors are valid. Truthy values are cached by metamodel identity, artifact type, and attribute name.

## 6. ID schemas

The grammar permits:

- `{num}`;
- `{num:N}` for minimum zero-padding;
- `{atype}`;
- literal quoted/unquoted schema text.

Invalid placeholders are rejected by the transformer. Validation rejects more than one `{num}` macro per schema. ID matching/number extraction is performed by `id_utils` consumers.

ID schema semantics used elsewhere:

- `{num:3}` means at least three digits;
- values wider than the padding remain untruncated;
- `{atype}` expands to the artifact type;
- schemas without `{num}` cannot participate in numeric renumbering.

## 7. Boolean and attribute semantics

- Default boolean accepted textual values are `true/false`, `yes/no`, `1/0`.
- Custom boolean declarations replace the default truthy/falsy sets for condition/type validation.
- Multiple attributes are list-valued and may have repeated source declarations.
- `contents` is an ordinary DSL-declared mandatory field with special downstream semantic use as artifact body.
- `id` is mandatory by model invariant but is parsed through a dedicated rule.

## 8. Runtime consumers

- Extraction uses type/multiple/reference rules while building fields.
- Tree population uses `reference to parent` rules.
- Artifact validation uses active conditions, types, multiplicity, extra-field rules, ID schemas, and traces.
- Editing uses ID schemas for preservation/renumbering.
- Publishing uses metamodel attributes for mandatory-field presence rendering.
- Task generation can inject implicit task types when configured.

## 9. Failure and evidence status

- Syntax errors, invalid placeholders, missing mandatory ID/contents rules, invalid anchors, and invalid schemas are fatal during model load.
- `validate=False` is available for parser-focused callers/tests and skips semantic validation.
- **Confirmed:** grammar forms, normalized structures, mandatory ID/contents, conditional-anchor rules, custom booleans, and schema macro restrictions.
- **`UNVERIFIED`:** exact diagnostics for unknown trace target types and behavior of legacy/mock metamodel dictionaries outside the current normalized shape.
