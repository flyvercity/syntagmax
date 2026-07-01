The users want a capability to make non-artifact fragments with special markers, such a commentary markers `[COM]`. These markers shall be configured on the input record level.

These markers will be used to influence publication.

In this version, the feature is requested for Obsidian Driver only.

The markers shall be case-insensitive.

Implementation-wise, general (unmarked) text blocks may be considered marked with some kind of default mark (e.g. `_REGULAR_`).

## Example

For example, consider the following config:

```toml
[[input]]
name = "system-requirements"
dir = "SYS"
driver = "obsidian"
markers = ["COM", "NOTE"]
```

The following example text shall have the following parts extracted:
- Regular text block
- Comment block
- Note block
- Regular block
- Requrement

```text
This is a sample preamble text. [COM]This is a special comment text [/COM].
[note]This a a special note text[/note]
Some more text
[SYS]This is a text for the requirement[ID]SYS-000[/SYS]
```
