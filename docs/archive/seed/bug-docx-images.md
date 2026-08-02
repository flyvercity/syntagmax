# DOCX Image Publication Bug

Ways to repoduce:
- clear output `reports` dir
- run publishing: docx has no images (expected - it has). Note that output markdown is OK.
- re-run publishing (do not clear reports): docx has images

Publishing command: `uv run syntagmax --cwd ..\..\example-project\  publish SCHED --docx --date-suffix`
