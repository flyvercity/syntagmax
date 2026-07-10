# Task 10: Update documentation

## Objective

Update `docs/reference/obsidian.md` fragment markers section to document the new ID syntax, validation rules, and auto-generation behavior.

## Target File

`docs/reference/obsidian.md` — Fragment Markers section (around line 195)

## Implementation

1. Replace the "numbered variants" mention in the Line-Prefix Markers subsection:
   - Old: `Also supports numbered variants: [COM 1], [NOTE 2].`
   - New: Document the ID syntax `[COM my-id]`

2. Add a new subsection "Block IDs" documenting:
   - Optional ID syntax for all three formats
   - Valid ID characters: `[a-zA-Z0-9_-.]`
   - Auto-generation behavior (deterministic short hash when omitted)
   - Uniqueness rules (explicit IDs must be unique per marker type globally)
   - Invalid ID error behavior

3. Update examples to show ID syntax:
   ```markdown
   [COM com-1]This is an identified comment.[/COM]
   [COM intro]This unclosed comment has an ID.

   [COM section.1] This line-prefix comment has an ID.
   ```

4. Add validation rules to the existing Validation Rules subsection.

## Acceptance Criteria

1. "Numbered variants" language removed
2. New ID syntax documented for all three marker formats
3. Validation rules listed
4. Auto-generation behavior explained
5. Examples show both with-ID and without-ID usage

## Dependencies

None — documentation only.

## Parallelization

Can run in parallel with all other tasks. No dependencies.
