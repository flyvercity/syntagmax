# Marker Renumber Command

- New command group: `markers`
- New command: renumber
- Search all non-artifact marked blocks without IDs
- For each add an unique id as nonsequitive block number. Start from the `max + 1`. To determine `max`, scan existing marked blocks. If none, start from zero.
- numbering is independent froe each marker type.
