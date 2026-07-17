# Export Artifact Tree as Tracing Tables

Users need to export artifacts if a form of a traceabilty matrix `Child ID -> Parent ID` or a reverse traceability matrix `Parent ID -> Child ID`.

## Basic Export

The basic format is CSV.

The output contains:
- Sequential Record Number
- Lead ID (child for forward, parent for reverse)
- Linked ID (parent for forward, child for reverse)
- A number of lead object's attributes, as requested

On row per lead object.

## Execution:

```bash
uv run syntagmax trace [OPTIONS]
```

New pptions:

- `--child <type>` -- the `atype` of lead objects (required)
- `--parent <type>` -- the `atype` of linked objects (required)
- `--attribute <name>` -- additional attributes of lea (optional, can be multiple)
- `--flat`` -- if there are multiple linked object, combine them into a single record with semi-colon-separated list (optional flag). Should work for both forward and backward.
- `--plugin <name>` -- use a plugin instead of CVS

## Plugin Support

Extend the plugin system with a new method that receives a matrix object ready for export. Plugins may use any other format of export besides CSV.

# Examples

### Example Forward Matrix Format

| RecordNumber | ChildID | ParentID | ChildAttrA   | ChildAttrB   |
| ------------ | ------- | -------- | ------------ | ------------ |
| 1            | LLR-001 | HLR-001  | custom-val-a | custom-val-b |
| 2            | LLR-002 | HLR-002  | custom-val-c | custom-val-d |
| 3            | LLR-002 | HLR-003  | custom-val-c | custom-val-d |

### Example Forward Matrix Format (Plattebed)

| RecordNumber | ChildID | ParentID | ChildAttrA   | ChildAttrB   |
| ------------ | ------- | -------- | ------------ | ------------ |
| 1            | LLR-001 | HLR-001  | custom-val-a | custom-val-b |
| 2            | LLR-002 | HLR-002; HLR-003 | custom-val-c | custom-val-d |

### Example Reverse Matrix Format

| RecordNumber | ParentID | ChildID | ParentAttrA  | ParentAttrB  |
| ------------ | -------- | --------| ------------ | ------------ |
| 1            | HLR-001  | LLR-001 | custom-val-a | custom-val-b |
| 1            | HLR-001  | LLR-001 | custom-val-a | custom-val-b |
| 1            | HLR-001  | LLR-001 | custom-val-a | custom-val-b |


## Additional Tasks

- Update `README.md` and `docs\technical-summary.md` accordingly
- Generate an example plugin that uses tab-separated format instead on CSV. Add an own README for this plugin example.