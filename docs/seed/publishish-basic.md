We need modify parsing system so to prepare the publishing system. 

In the current implementation, the drivers read inputs and produce an artifact tree.

We need to create an intermediate representation the inputs, let's call it a block tree, that preserves:
- the structure of the inputs
- the non-requirement texts.

This representation shall not be use for analysis like `impact`,`metrics`, or `ai`. Only for publishing.

The structure may look like this:

```
ROOT-BLOCK
  -  Input Repord A
     - Text Blcok
     - Requirement Block
     - Requirement Block
     - Text Block
     - Requirement Block
  - Input Record B
```

All files in each record shall be parsed in lexicographical order by their filenames, blocks within each file - in their naturual order.

Add a new command `publish <output-file>`, a rudimentary version for now, that will combine the whole block tree into a single structured markdown file, without losing any non-artifact text.
