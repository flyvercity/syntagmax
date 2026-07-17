We need to modify the parsing system to prepare for the publishing system.

In the current implementation, drivers read inputs and produce an artifact tree.

We need to create an intermediate representation of the inputs (a "block tree") that preserves:
- the structure of the inputs
- the non-requirement texts.

This representation shall not be use for analysis like `impact`,`metrics`, or `ai`. Only for publishing.

The structure may look like this:

```
ROOT-BLOCK
  -  Input Record A
     - Text Block
     - Requirement Block
     - Requirement Block
     - Text Block
     - Requirement Block
  - Input Record B
```

All files in each record shall be parsed in lexicographic order by filename; blocks within each file are in their natural order.

Add a new command `publish <output-file>`, a rudimentary version for now, that will combine the whole block tree into a single structured markdown file, without losing any non-artifact text.
