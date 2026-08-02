# Analysis Report


## Errors

Total errors: 4


1. The repository for the base C:\Users\boris\projects\flyvercity\stmx-ws\stmx\syntagmax\example\obsidian-driver\SYS is dirty. Commit your changes or use --allow-dirty-worktree.

2. The repository for the base C:\Users\boris\projects\flyvercity\stmx-ws\stmx\syntagmax\example\obsidian-driver\REQ is dirty. Commit your changes or use --allow-dirty-worktree.

3. The repository for the base C:\Users\boris\projects\flyvercity\stmx-ws\stmx\syntagmax\example\obsidian-driver\src is dirty. Commit your changes or use --allow-dirty-worktree.

4. The repository for the base C:\Users\boris\projects\flyvercity\stmx-ws\stmx\syntagmax\example\obsidian-driver\tests is dirty. Commit your changes or use --allow-dirty-worktree.






## Impact Analysis

Total suspicious links: 3


| Artifact | Parent | Required Revision | Actual Revision |
|----------|--------|-------------------|-----------------|
| REQ:REQ-003 | SYS:SYS-003 | older | 5784c50 (2026-06-20 21:07 by boris@flyver.city) |
| REQ:REQ-004 | SYS:SYS-003 | older | 5784c50 (2026-06-20 21:07 by boris@flyver.city) |
| SRC:SRC-001 | REQ:REQ-001 | older | 58f563a (2026-06-20 21:08 by boris@flyver.city) |



### Suspicious Tree

```text
ROOT
├─SYS:SYS-001
│ └─REQ:REQ-001 [*] UPDATED
│   └─SRC:SRC-001 [!] OUTDATED
└─SYS:SYS-003 [*] UPDATED
  ├─REQ:REQ-003 [!] OUTDATED
  └─REQ:REQ-004 [!] OUTDATED
```


