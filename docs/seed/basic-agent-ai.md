# Phase 1 Agentic Commands - AI-Close an Impact Task

This seed spec defines a general approach to ai commands for Syntagmax and the first pilot command to implement with this approach.

## General Approach

Syntagmax AI approach will be based, primarily, on interaction with local CLI AI Coding Agents to isolate the tool from complex harnessing and subscription issues. There is no intent to forbid API-calling AI once and for all, but the main burden shall be on agents. This first iteration doesn't use API-callin at all.

The general flow of the tool's AI use shall use the following flow:
- conventional assessment of the task
- prompt generation
- local agent invocation
- conventional agent output analysis
- task finalization 

The tool shall work with major CLI agents that support one-shot non-interactive mode.

For this version, start with these:
- Kiro CLI
- Antigravity CLI
- Mistral Vibe
- OpenCode
- Codex
- Copilot
- Claude Code

Authentication shall not be tool's concern. Agent support shall be easily extensible, e.g. using a YAML file with command line patterns.

All AI-enable command shall be grouped under `syntagmax ai` command group.

## First Coomand - AI Impact Task Verification

Use AI to verify is an impact task was correctly addressed and close it.

Command example: `syntagmax ai verify <path-to-task-file.md>`

Flow:
- Ensure that repo is not dirty. Abort unless `--allow-dirty` is given
- Read the file: shall be Markdown with frontmatter IDs (`simple-markdown` driver)
- Detect file contents type by id.
  - For this version, only support impact tasks, with IDs like `TASK-IMPACT-<parent-id>-<child-id>`
  - if contents are not supported, report a fatal error and abort
- Ensure that the task status is `open`
- Create a prompt for a CLI agent to verify task completion:
  - Analyze parent's content and history
  - Analyze child's content and history
  - Assess if the child was changed to be up-to-date with the parent
  - Append agent's report to the task file 
  - Mark the task `closed` if appropriate
- Verify a new state of the task:
  - it is not malformed
  - it has the same id
  - if is either `open` or `closed`
- Report the result to the used: "the task was verified and closed" or 'the task reqiures more work"

Note: the agent shall use the currect working tree versions of the artifacts, not those recorded in the task. An agent can, however, use `git` or `gh` to explore the changes made since task's creation.


### Agent's Prompt

[BRAINSTORM]


## Future Considerations

Async call to a cloud agent can also be supported in future if reasonable (i.e., Jules, Copilot Cloud, Kiro Web, etc.)
