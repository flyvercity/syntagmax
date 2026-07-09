# Pre-Publishing Filter Plugin Hook

This plugin hook shall receive blocks one by one and return a modified block. In shall not manupulate block lists.


## New Options

- `--pre-filter <plugin-name>`


## Constraints

- pre-publishing filter shall not disrupt workings of publishing plugins
- one plugin can implement both hooks