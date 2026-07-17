**THIS IS WIP - DO NOT USE**
- **`--doors`** *(Optional)*: Activates identifier and attribute replacement mode.
- **`--mapping <csv>`** *(Optional)*: Path to the CSV file mapping keys to replacement values for DOORS mode.


Naming convention:
```
<output_dir>/
    <INPUT_RECORD_NAME>_<YYYY-MM-DD>.md    ← Assembled Markdown document
    <INPUT_RECORD_NAME>_<YYYY-MM-DD>.docx  ← Final Word document (optional, generated if --docx is requested)
```

### 6.3. DOORS Replacement Mode
1. When `--doors` and `--mapping <csv>` are provided, load the CSV mapping table.
2. Iterate through parsed blocks.
3. Replace requirement IDs, object IDs, and designated attribute values using the mapping.
4. If a value does not exist in the mapping file, preserve the original value.
5. Record the number of successful replacements in the publication log.
  
Logging:
  - Details on DOORS replacements and Pandoc exit status
