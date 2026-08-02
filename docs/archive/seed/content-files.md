# Special "Content" Files

The publishing engine uses filenames as headers. Sometimes this is undesirable. Users want to use special naming — a filename containing a special marker — to treat the file's content directly, not as a separate section.

- Default marker is `_contents_`
- The marker shall be a configurable publish config option (`contents_marker` in `publish.yaml`)
