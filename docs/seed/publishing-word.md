# Publishing to MS Word and PDF via Pandoc

Expand publishing to produce MS Word and PDF documents.

## New CLI Options

- **`--docx`**: Attempts to run Pandoc to compile a Word document alongside the Markdown.
- **`--pdf`**: Attempts to run Pandoc to compile a PDF document alongside the Markdown.

### DOCX/PDF Export (Pandoc Integration)

1. Generate the standard Markdown output file.
2. If the `--docx` or `--pdf` flag is present, check for the presence of the `pandoc` executable.
3. If Pandoc is available, run it to convert the Markdown to DOCX and/or PDF.
4. If Pandoc is absent or fails, log the error to the publication log, preserve the successfully generated Markdown file, and exit successfully (do not crash).
  
## Additional Logging:
  - Pandoc exit status
