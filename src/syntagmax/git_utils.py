# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Git utilities for extracting history and revisions.

import git
import logging as lg
from datetime import datetime
from pathlib import Path
from syntagmax.artifact import ArtifactMap, Revision, LineLocation, FileLocation
from syntagmax.config import Config


def is_dirty(config: Config) -> bool:
    try:
        repo = git.Repo(config.base_dir(), search_parent_directories=True)
        return repo.is_dirty() or len(repo.untracked_files) > 0
    except git.InvalidGitRepositoryError:
        lg.warning("Not a git repository, assuming not dirty.")
        return False
    except git.exc.NoSuchPathError:
        lg.warning("Repository path does not exist, assuming not dirty.")
        return False


def populate_revisions(config: Config, artifacts: ArtifactMap):
    """
    Populate revisions for each artifact in the map using git history.
    """
    try:
        repo = git.Repo(config.base_dir(), search_parent_directories=True)
        repo_root = Path(repo.working_tree_dir).absolute()
    except git.InvalidGitRepositoryError:
        lg.warning("Not a git repository, skipping revision extraction.")
        return

    for artifact in artifacts.values():
        revisions = set()
        base_dir = Path(config.base_dir())
        lg.debug(f"Processing revisions for artifact {artifact.aid} at {artifact.location}")
        if isinstance(artifact.location, LineLocation):
            # Paths in artifacts are relative to config.base_dir()
            # We need them relative to repo_root for git
            abs_path = (base_dir / artifact.location.loc_file).absolute()
            try:
                rel_repo_path = abs_path.relative_to(repo_root)
                start, end = artifact.location.loc_lines
                lg.debug(f"Blaming {rel_repo_path} lines {start}-{end}")
                # git blame returns a list of (Commit, list of lines)
                for commit, _ in repo.blame(None, str(rel_repo_path), L=f"{start},{end}"):
                    revisions.add(Revision(
                        hash_long=commit.hexsha,
                        hash_short=commit.hexsha[:7],
                        timestamp=datetime.fromtimestamp(commit.committed_date),
                        author_email=commit.author.email
                    ))
                lg.debug(f"Found {len(revisions)} revisions for {artifact.aid}")
            except Exception as e:
                lg.debug(f"Failed to blame {artifact.location.loc_file}: {e}")

        elif isinstance(artifact.location, FileLocation):
            # Last commit for the file itself
            paths = [artifact.location.loc_file]
            if artifact.location.loc_sidecar:
                paths.append(artifact.location.loc_sidecar)
            
            for path in paths:
                abs_path = (base_dir / path).absolute()
                try:
                    rel_repo_path = abs_path.relative_to(repo_root)
                    lg.debug(f"Getting history for {rel_repo_path}")
                    # Use repo.iter_commits('HEAD', paths=path, max_count=1) for both the file and its sidecar
                    for commit in repo.iter_commits('HEAD', paths=str(rel_repo_path), max_count=1):
                         revisions.add(Revision(
                            hash_long=commit.hexsha,
                            hash_short=commit.hexsha[:7],
                            timestamp=datetime.fromtimestamp(commit.committed_date),
                            author_email=commit.author.email
                        ))
                except Exception as e:
                    lg.debug(f"Failed to get history for {path}: {e}")
            lg.debug(f"Found {len(revisions)} revisions for {artifact.aid}")
        
        artifact.revisions = revisions
