Reviewing the code, I suspect that two parsing procedures are in place, like this
- Publish Command -> Extract Blocks -> Publish
- Analyze Command -> Extract Artifacts -> Analyze

However, I expect the following will be architecturally cleaner:
- Publish Command -> Extract Blocks -> Publish
- Analyze Command -> Extract Blocks -> Extract Artifacts from Blocks -> Analyze

Confirm the situation. If two, assess feasibility of the second option.