# Prepare a new release of the tool.

Preconditions:
- if not on the `main` branch, abort

Steps:
- bump up the version
- amend the CHANGELOG
- update the landing page contents
- present to the user command for next steps (commit, tag with a comment, push). Do not execute without user's confirmation.

## Changelog Generation

Keep the change log more product-oriented, avoid too much technical detail.

## Landing Page Update

Consider updating the landing page to reflect new features, but keep it concise and avoid bloating. Ask if unsure.

## Notes

There is no need to use `uv build` and `uv publish`. The GHA workflow handles these.

Note that the proper tag format is `YYYY.MM.DD` padded with zeros, e.g. `2026.01.01`, not `vYYYY.MM.DD`.
