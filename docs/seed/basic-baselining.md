# Basic Baselining Command

## CLI Command

```bash
syntagmax change baseline <tag-name>
```

- This command shall create the same git tag in all affected repositories (i.e., all repos input records point to)
- The command shall not tag any repo if there are dirty repos
- `config.toml` can optionally specify a regex for the tags to conform to