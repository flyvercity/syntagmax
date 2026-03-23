# Schema Validation in Metamodel DSL

## Goal
Validate the `as <schema>` clause in the metamodel DSL to ensure it only contains valid placeholders: `{atype}`, `{num}`, and `{num:padding}`. Any other placeholder or incorrect syntax (e.g., `{invalid}`, `{num:abc}`) should yield a clear error during metamodel loading.

## Approach: Grammar-Level Validation
We will redefine the `schema_value` rule in the Lark grammar to explicitly define its structure. This will allow the parser to identify placeholders and literals as distinct entities.

### Grammar Changes (`src/syntagmax/metamodel.lark`)

```lark
# Before:
# ?schema_value: ESCAPED_STRING | SCHEMA
# SCHEMA: /[^ \t\n\r"]+/

# After:
?schema_value: unquoted_items | quoted_items

unquoted_items: (SCHEMA_PART | placeholder | invalid_placeholder)+
quoted_items: "\"" (QUOTED_PART | placeholder | invalid_placeholder)* "\""

placeholder: "{" ( "atype" | "num" [ ":" INT ] ) "}"
invalid_placeholder: "{" /[^}]*/ "}"

SCHEMA_PART: /[^ \t\n\r"{]+/
QUOTED_PART: /[^"{]+/

%import common.INT
```

### Transformer Changes (`src/syntagmax/metamodel.py`)

The `DSLTransformer` will be updated to:
- Handle `unquoted_items` and `quoted_items` by joining their children strings.
- Handle `placeholder` by reconstructing the placeholder string.
- Handle `invalid_placeholder` by raising a `ValueError` with a descriptive message.

```python
class DSLTransformer(Transformer):
    # ... existing methods ...

    def unquoted_items(self, children):
        return "".join(map(str, children))

    def quoted_items(self, children):
        return "".join(map(str, children))

    def placeholder(self, children):
        if str(children[0]) == "atype":
            return "{atype}"
        else:
            # it's num
            if len(children) > 1 and children[1] is not None:
                return f"{{num:{children[1]}}}"
            return "{num}"

    def invalid_placeholder(self, children):
        content = str(children[0])
        raise ValueError(f"Invalid placeholder: {{{content}}}")

    def rule(self, children):
        # ...
        # Handle the "id" rule
        else:
            # children: type_info, [schema]
            schema = children[1] if len(children) > 1 and children[1] is not None else None
            return {
                'name': 'id',
                'presence': 'mandatory',
                'multiple': False,
                'type_info': children[0],
                'schema': schema,
                'id_rule': True,
            }
```

## Testing Strategy
1. **Failing Test**: Add a test case with an invalid placeholder (e.g., `id is string as REQ-{invalid}`) and verify it raises a `FatalError` with the message `Invalid placeholder: {invalid}`.
2. **Success Test**: Add a test case with valid placeholders (e.g., `id is string as REQ-{atype}-{num:4}`) and verify it loads correctly.
3. **Quoted Schema Test**: Verify that quoted schemas with spaces also validate correctly.
