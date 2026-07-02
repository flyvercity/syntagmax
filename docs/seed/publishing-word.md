**THIS IS WIP - DO NOT USE**
- **`--docx`** *(Optional)*: Attempts to run Pandoc to compile a Word document alongside the Markdown.

### 6.2. DOCX Export (Pandoc Integration)
1. Generate the standard Markdown output file.
2. If the `--docx` flag is present, check for the presence of the `pandoc` executable.
3. If Pandoc is available, run it to convert the Markdown to DOCX.
4. If Pandoc is absent or fails, log the error to the publication log, preserve the successfully generated Markdown file, and exit successfully (do not crash).
  
Logging:
  - Details on DOORS replacements and Pandoc exit status
