# Obsidian Setting Exports

Some Obsidian-specific inputs store attachments, especially images, in a folder specified in Vault Settings.

The tool need to optionally use this path to lookup images during publications.

By default, the settings are located in `.obsidian` directory (sibling to `.syntagmax`). In `.obsidian` directory there is a file named `app.json`. The option we need is `attachmentFolderPath`.

## `app.json` Example

```json
{
  "promptDelete": false,
  "pdfExportSettings": {
    "includeName": false,
    "pageSize": "A4",
    "landscape": false,
    "margin": "0",
    "downscalePercent": 100
  },
  "newLinkFormat": "shortest",
  "attachmentFolderPath": "attachments/pics",
  "useMarkdownLinks": false,
  "alwaysUpdateLinks": true,
  "showLineNumber": true,
  "readableLineLength": false
}
```

## New Obsidian Driver Integrations Options

- `[obsidian.integration]` - enable Obsidian integration (boolean)
- `[obsidian.root]` - optionally point the tool to another directory instead on `<project-root>/.obsidian`
