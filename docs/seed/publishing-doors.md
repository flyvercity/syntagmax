** FOR AGENTS: THIS IS WORK-IN-PROGRESS, DO NOT USE**

# DOORS Integration Support for Publishing

## New CLI Options

- **`--doors`**: Activates identifier and attribute replacement mode.
- **`--mapping <csv>`**: Path to the CSV file mapping keys to replacement values for DOORS mode.

## DOORS Replacement Mode

1. When `--doors` and `--mapping <csv>` are provided, load the CSV mapping table.
2. Iterate through parsed blocks.
3. Replace requirement IDs, object IDs, and designated attribute values using the mapping.
4. If a value does not exist in the mapping file, preserve the original value.
5. Record the number of successful replacements in the publication log.
  
# Additional Logging

- Details on DOORS replacements
