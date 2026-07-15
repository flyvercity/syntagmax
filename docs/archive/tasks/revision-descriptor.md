# Revision Descriptor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attach a revision descriptor (set of git commits) to each artifact and render it when `--render-tree` is used. Provide a `--no-git` flag to skip this.

**Architecture:** 
1. Update `Params` and `cli.py` to support `--no-git`.
2. Update `Artifact` model and `FileLocation` to store revision-related data.
3. Create `src/syntagmax/git_utils.py` to handle git history extraction using `GitPython`.
4. Update `process` in `main.py` to extract revisions after artifacts are built.
5. Update `render.py` to display revisions.

**Tech Stack:** Python, GitPython, Click, Rich.

---

### Task 1: Update CLI and Params

**Files:**
- Modify: `src/syntagmax/params.py`
- Modify: `src/syntagmax/cli.py`

- [ ] **Step 1: Add no_git to Params**
```python
class Params(TypedDict):
    verbose: bool
    render_tree: bool
    ai: bool
    cwd: str
    no_git: bool
```

- [ ] **Step 2: Add --no-git option to Click group in cli.py**
```python
@click.option('--no-git', is_flag=True, help='Skip git history extraction')
```

- [ ] **Step 3: Update Params mapping in rms group**
```python
    ctx.obj = Params(**kwargs)  # type: ignore
```

### Task 2: Update Artifact Model and Locations

**Files:**
- Modify: `src/syntagmax/artifact.py`
- Modify: `src/syntagmax/extractors/sidecar.py`

- [ ] **Step 1: Update FileLocation in artifact.py**
```python
class FileLocation(Location):
    def __init__(self, loc_file: str, loc_sidecar: str | None = None):
        self.loc_file = loc_file
        self.loc_sidecar = loc_sidecar

    def __str__(self) -> str:
        if self.loc_sidecar:
            return f"{self.loc_file} (sidecar: {self.loc_sidecar})"
        return self.loc_file
```

- [ ] **Step 2: Add Revision class and update Artifact in artifact.py**
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Revision:
    hash_long: str
    hash_short: str
    timestamp: datetime
    author_email: str

    def __eq__(self, other):
        if not isinstance(other, Revision):
            return False
        return self.hash_long == other.hash_long

    def __hash__(self):
        return hash(self.hash_long)

    def __str__(self) -> str:
        return f'{self.hash_short} by {self.author_email} at {self.timestamp}'
```
Add `self.revisions: set[Revision] = set()` to `Artifact.__init__`.

- [ ] **Step 3: Update SidecarExtractor in sidecar.py**
```python
        location = FileLocation(
            self._config.derive_path(filepath),
            self._config.derive_path(sidecar_path)
        )
```

### Task 3: Implement Git History Extraction

**Files:**
- Create: `src/syntagmax/git_utils.py`

- [ ] **Step 1: Implement populate_revisions function**
```python
import git
import logging as lg
from datetime import datetime
from syntagmax.artifact import ArtifactMap, Revision, LineLocation, FileLocation
from syntagmax.config import Config

def populate_revisions(config: Config, artifacts: ArtifactMap):
    try:
        repo = git.Repo(config.base_dir(), search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        lg.warning("Not a git repository, skipping revision extraction.")
        return

    for artifact in artifacts.values():
        revisions = set()
        if isinstance(artifact.location, LineLocation):
            file_path = artifact.location.loc_file
            start, end = artifact.location.loc_lines
            # git blame -L start,end file
            try:
                for commit, lines in repo.blame(None, file_path, L=f"{start},{end}"):
                    revisions.add(Revision(
                        hash_long=commit.hexsha,
                        hash_short=commit.hexsha[:7],
                        timestamp=datetime.fromtimestamp(commit.committed_date),
                        author_email=commit.author.email
                    ))
            except Exception as e:
                lg.debug(f"Failed to blame {file_path}: {e}")

        elif isinstance(artifact.location, FileLocation):
            # Last commit for the file itself
            file_paths = [artifact.location.loc_file]
            if artifact.location.loc_sidecar:
                file_paths.append(artifact.location.loc_sidecar)
            
            for path in file_paths:
                try:
                    for commit in repo.iter_commits(paths=path, max_count=1):
                         revisions.add(Revision(
                            hash_long=commit.hexsha,
                            hash_short=commit.hexsha[:7],
                            timestamp=datetime.fromtimestamp(commit.committed_date),
                            author_email=commit.author.email
                        ))
                except Exception as e:
                    lg.debug(f"Failed to get history for {path}: {e}")
        
        artifact.revisions = revisions
```

### Task 4: Integrate Extraction into Main Loop

**Files:**
- Modify: `src/syntagmax/main.py`

- [ ] **Step 1: Call extraction in process()**
```python
    if not config.params.get('no_git', False):
        try:
            from syntagmax.git_utils import populate_revisions
            populate_revisions(config, artifacts)
        except ImportError:
            lg.warning("GitPython not installed, skipping revision extraction.")
        except Exception as e:
            lg.warning(f"Failed to extract git revisions: {e}")
    else:
        lg.warning("Git history extraction skipped (--no-git)")
```

### Task 5: Update Rendering

**Files:**
- Modify: `src/syntagmax/render.py`

- [ ] **Step 1: Update print_artifact to show revisions**
```python
    if artifact.revisions:
        rev_list = sorted(list(artifact.revisions), key=lambda r: r.timestamp, reverse=True)
        revisions_str = ", ".join([r.hash_short for r in rev_list])
        u.pprint(f'{detail_indent}\tRevisions: [{revisions_str}]')
```

### Task 6: Testing

**Files:**
- Create: `tests/test_git_revisions.py`

- [ ] **Step 1: Write test for git extraction**
Mock `git.Repo` and verify `populate_revisions` correctly fills `artifact.revisions`.
