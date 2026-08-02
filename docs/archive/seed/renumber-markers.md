# Marker Renumber Command

- New command group: `markers`
- New command: renumber
- Search all non-artifact marked blocks without IDs
- For each add a unique id as a consecutive block number. Start from the `max + 1`. To determine `max`, scan existing marked blocks. If none, start from 1.
- Numbering is independent for each marker type.
