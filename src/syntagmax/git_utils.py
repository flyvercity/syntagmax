# SPDX-License-Identifier: MIT

# Author: Boris Resnick
# Created: 2025-03-29
# Description: Git utilities for extracting history and revisions.

import git
import logging as lg
from datetime import datetime
from pathlib import Path
from syntagmax.artifact import ArtifactMap, Revision, LineLocation, FileLocation, Artifact
from syntagmax.config import Config


class RepoCache:
    def __init__(self, config: Config):
        self.config = config
        self.repos = {}
        self.repo_roots = {}

    def get_repo(self, artifact: Artifact, errors: list[str]):
        base = self.config.base_dir()

        art_base = Path(base, artifact.location.filepath()).parent.absolute().resolve()

        repo = self.repos.get(art_base)
        repo_root = self.repo_roots.get(art_base)

        if repo:
            return repo, repo_root

        try:
            lg.info(f'Derived git repo: {art_base}')
            repo = git.Repo(art_base, search_parent_directories=True)
            is_dirty = repo.is_dirty() or len(repo.untracked_files) > 0

            # Check for dirty worktree
            if is_dirty and not self.config.params.get('allow_dirty_worktree', False):
                errors.append(
                    f'The repository for the base {art_base} is dirty. Commit your changes or use --allow-dirty-worktree.'
                )

            repo_root = Path(repo.working_tree_dir).absolute()
            self.repos[art_base] = repo
            self.repo_roots[art_base] = repo_root
            return repo, repo_root

        except git.InvalidGitRepositoryError:
            errors.append(f'Not a git repository, skipping revision extraction for {artifact.aid}.')
            return None, None


def populate_revisions(config: Config, artifacts: ArtifactMap, errors: list[str]):
    """
    Populate revisions for each artifact in the map using git history.
    """
    repos = RepoCache(config)

    for artifact in artifacts.values():
        if artifact.atype == 'ROOT':
            continue

        repo, repo_root = repos.get_repo(artifact, errors)

        if not repo:
            lg.warning(f'Could not get repo for artifact {artifact.aid}, skipping.')
            continue

        revisions = set()
        base_dir = Path(config.base_dir())
        lg.debug(f'Processing revisions for artifact {artifact.aid} at {artifact.location}')

        if isinstance(artifact.location, LineLocation):
            # Paths in artifacts are relative to config.base_dir()
            # We need them relative to repo_root for git
            abs_path = (base_dir / artifact.location.loc_file).absolute().resolve()

            rel_repo_path = abs_path.relative_to(repo_root)
            start, end = artifact.location.loc_lines
            lg.debug(f'Blaming {rel_repo_path} lines {start}-{end}')
            # git blame returns a list of (Commit, list of lines)
            for commit, _ in repo.blame(None, str(rel_repo_path), L=f'{start},{end}'):
                revisions.add(
                    Revision(
                        hash_long=commit.hexsha,
                        hash_short=commit.hexsha[:7],
                        timestamp=datetime.fromtimestamp(commit.committed_date),
                        author_email=commit.author.email,
                    )
                )
            lg.debug(f'Found {len(revisions)} revisions for {artifact.aid}')

        elif isinstance(artifact.location, FileLocation):
            # Last commit for the file itself
            paths = [artifact.location.loc_file]
            if artifact.location.loc_sidecar:
                paths.append(artifact.location.loc_sidecar)

            for path in paths:
                abs_path = (base_dir / path).absolute().resolve()

                rel_repo_path = abs_path.relative_to(repo_root)
                lg.debug(f'Getting history for {rel_repo_path}')
                # Use repo.iter_commits('HEAD', paths=path, max_count=1) for both the file and its sidecar
                for commit in repo.iter_commits('HEAD', paths=str(rel_repo_path), max_count=1):
                    revisions.add(
                        Revision(
                            hash_long=commit.hexsha,
                            hash_short=commit.hexsha[:7],
                            timestamp=datetime.fromtimestamp(commit.committed_date),
                            author_email=commit.author.email,
                        )
                    )

            lg.debug(f'Found {len(revisions)} revisions for {artifact.aid}')

        artifact.revisions = revisions
