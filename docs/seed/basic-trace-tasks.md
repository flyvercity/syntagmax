# Task Subsystem - Phase I Change Reports from Impact Analysis

We are adding a new capability to Syntagmax - Tasks.

- Tasks are still markdown artifacts
- One markdown file - one task
- attributes in fronmatter
- task description in the body
- a task can have an `atype` and described by the metamodel
- default `atype` is `TASK`. If there is no metamodel for TASK, an implicit metamodel shall be defined with mandatory attributes only.
- Mandatory task artifact attributes:
  - `id`
  - `contents`
  - `status` (`open`, `closed`)

## Configuration (`config.yaml`)

### Global

- task files location (default: `tasks/`, resolved relative to config file directory → `.syntagmax/tasks/`)

### Impact Section 

- task generation enabled/disabled
- task file location override (optional)
- task `atype` mapping from impact analysis artifact pair (parent atype/target atype) to task atype. By default: `(any, any) -> TASK`

## Task Generation

- for each outdated artifact (as a result of impact analysis), generate a dedicated task
- a unique `id` shall be generated
- task description shall include:
  - Full references to parent (input record, relative file path, full commit hash, short commit hash)
  - Full references to child (input record, relative file path, full commit hash, short commit hash)
  - the essence of task, i.e. to check of the child is updated properly

  