# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Git utilities for extracting history and revisions.

import git
import logging as lg
from datetime import datetime
from syntagmax.artifact import ArtifactMap, Revision, LineLocation, FileLocation
from syntagmax.config import Config


def populate_revisions(config: Config, artifacts: ArtifactMap):
    """
    Populate revisions for each artifact in the map using git history.
    """
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
                # git blame returns a list of (Commit, list of lines)
                for commit, _ in repo.blame(None, file_path, L=f"{start},{end}"):
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
                    # Use repo.iter_commits(paths=path, max_count=1) for both the file and its sidecar
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
