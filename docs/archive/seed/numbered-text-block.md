# Non Artifact Block Identification

Add a capability to identify non-artifact blocks:

- ids shall contain `[a-zA-Z0-9_-\.]` symbols only
- if absent, the tool generates a new UUID internally
- ids shall be unique within a given marker type. Violations shall be added to extraction errors.

## Syntax

No ID, default:

```text
[COM]This is a commentary block
```

With ID:

```text
[COM com-1]This is an identified commentary block
```
