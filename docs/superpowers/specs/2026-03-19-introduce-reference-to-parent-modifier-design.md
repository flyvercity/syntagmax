# Design Spec - Introduce "reference to parent" Attribute Modifier

## Status: Draft
## Date: 2026-03-19

## Goal
Enhance the Metamodel DSL to allow marking `reference` attributes as parent indicators using the `to parent` modifier. These attributes will automatically populate the `Artifact.pids` list, which is used to build the artifact hierarchy.

## User Requirements
- Introduce new syntax: `attribute <name> is [mandatory|optional] [multiple] reference to parent`.
- Multiple attributes can be marked as `to parent`.
- Support both singular and multiple reference attributes.
- Populate `Artifact.pids` from these attributes before tree construction.
- Remove hardcoded backward compatibility for the `pid` attribute name.
- Update `README.md`.

## Proposed Changes

### 1. Metamodel DSL Grammar (`src/syntagmax/metamodel.lark`)
Modify the `type_reference` rule to accept the optional `to parent` modifier.

```lark
?type: "string" -> type_string
     | "integer" -> type_integer
     | "boolean" -> type_boolean
     | "reference" ["to" "parent"] -> type_reference
     | "enum" "[" value ("," value)* "]" -> type_enum
```

### 2. Metamodel Transformer (`src/syntagmax/metamodel.py`)
Update `DSLTransformer.type_reference` to capture the `to_parent` modifier.

```python
    def type_reference(self, children):
        # If "to" and "parent" are present, children will contain them as tokens or strings
        # Depending on Lark config, we might need to check len(children)
        to_parent = any(str(c) == 'to' for c in children) # Simplified check
        return {'type': 'reference', 'to_parent': to_parent}
```

### 3. Artifact Builder (`src/syntagmax/artifact.py`)
Remove the hardcoded check for `pid` in `ArtifactBuilder.add_field`.

```python
# REMOVE:
# if field.lower() == 'pid':
#     try:
#         self.artifact.pids.append(ARef.coerce(value))
#     except Exception:
#         pass
```

### 4. Tree Construction (`src/syntagmax/tree.py`)
Implement a new function `populate_pids` (or add logic to `build_tree`) that iterates through all artifacts and uses the metamodel to find `to_parent` attributes.

```python
def populate_pids(config: Config, artifacts: ArtifactMap):
    if not config.metamodel:
        return

    for a in artifacts.values():
        if a.atype not in config.metamodel['artifacts']:
            continue
            
        rules = config.metamodel['artifacts'][a.atype]['attributes']
        for attr_name, rule in rules.items():
            type_info = rule.get('type_info', {})
            if type_info.get('type') == 'reference' and type_info.get('to_parent'):
                val = a.fields.get(attr_name)
                if not val:
                    continue
                
                # Support both multiple and singular
                refs = val if rule.get('multiple') else [val]
                for ref_str in refs:
                    try:
                        ref = ARef.coerce(ref_str)
                        if ref not in a.pids:
                            a.pids.append(ref)
                    except Exception:
                        # Validation will catch malformed references later in analysis
                        pass
```

### 5. Main Execution Flow (`src/syntagmax/main.py`)
Ensure `populate_pids` is called before `build_tree`.

## Verification Plan

### Automated Tests
1. **Metamodel Parsing**:
   - Verify `reference to parent` is correctly parsed into `to_parent: True`.
   - Verify plain `reference` is parsed into `to_parent: False`.
2. **PID Population**:
   - Test with singular `reference to parent`.
   - Test with `multiple reference to parent`.
   - Test with multiple different attributes marked as `to parent`.
   - Verify no duplicates in `Artifact.pids`.
3. **Hierarchy Building**:
   - Verify `build_tree` correctly uses the populated `pids` to establish parent-child relationships.
4. **Regression**:
   - Verify that an attribute named `pid` is NOT automatically treated as a parent unless marked `to parent`.

### Manual Verification
- Run a sample project with the new DSL syntax and verify the generated tree output.
