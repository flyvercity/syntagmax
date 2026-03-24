# SPDX-License-Identifier: MIT
import pytest
import git
from syntagmax.config import Config
from syntagmax.params import Params
from syntagmax.artifact import Artifact, FileLocation, LineLocation
from syntagmax.git_utils import populate_revisions, is_dirty


@pytest.fixture
def git_repo(tmp_path):
    repo = git.Repo.init(tmp_path)
    # Create a file and commit it
    test_file = tmp_path / 'test.txt'
    test_file.write_text('line 1\nline 2\nline 3\n', encoding='utf-8')
    repo.index.add([str(test_file.relative_to(tmp_path))])
    repo.index.commit('Initial commit', author=git.Actor('Test Author', 'test@example.com'))

    # Another commit
    test_file.write_text('line 1\nline 2 changed\nline 3\n', encoding='utf-8')
    repo.index.add([str(test_file.relative_to(tmp_path))])
    repo.index.commit('Second commit', author=git.Actor('Second Author', 'second@example.com'))

    return repo, tmp_path


@pytest.fixture
def config(tmp_path, git_repo):
    _, repo_path = git_repo
    cfg_path = repo_path / 'config.toml'
    cfg_path.write_text(
        """
base = "."
[[input]]
name = "test"
dir = "."
driver = "text"
atype = "requirement"
""",
        encoding='utf-8',
    )
    params = Params(verbose=False, render_tree=False, ai=False)
    return Config(params=params, config_filename=cfg_path)


def test_populate_revisions_file_location(config, git_repo):
    _, repo_path = git_repo
    artifacts = {}

    # Artifact with FileLocation
    art1 = Artifact(config)
    art1.aid = 'ART-1'
    art1.atype = 'req'
    art1.location = FileLocation('test.txt')
    artifacts['ART-1'] = art1

    populate_revisions(config, artifacts)

    assert len(art1.revisions) == 1
    rev = list(art1.revisions)[0]
    assert rev.author_email == 'second@example.com'
    assert len(rev.hash_short) == 7


def test_populate_revisions_line_location(config, git_repo):
    repo, repo_path = git_repo
    artifacts = {}

    # Artifact with LineLocation
    art1 = Artifact(config)
    art1.aid = 'ART-2'
    art1.atype = 'req'
    art1.location = LineLocation('test.txt', (2, 2))  # line 2 was changed in second commit
    artifacts['ART-2'] = art1

    art2 = Artifact(config)
    art2.aid = 'ART-3'
    art2.atype = 'req'
    art2.location = LineLocation('test.txt', (1, 1))  # line 1 was changed in first commit
    artifacts['ART-3'] = art2

    populate_revisions(config, artifacts)

    # Line 2 should have the second commit
    assert len(art1.revisions) == 1
    rev1 = list(art1.revisions)[0]
    assert rev1.author_email == 'second@example.com'

    # Line 1 should have the first commit
    assert len(art2.revisions) == 1
    rev2 = list(art2.revisions)[0]
    assert rev2.author_email == 'test@example.com'


def test_is_dirty_no_git(tmp_path):
    # Setup config in a non-git dir
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        """
base = "."
[[input]]
name = "test"
dir = "."
driver = "text"
atype = "requirement"
""",
        encoding='utf-8',
    )
    params = Params(verbose=False, render_tree=False, ai=False)
    config = Config(params=params, config_filename=cfg_path)

    assert not is_dirty(config)


def test_populate_revisions_no_git(tmp_path, caplog):
    # Setup config in a non-git dir
    cfg_path = tmp_path / 'config.toml'
    cfg_path.write_text(
        """
base = "."
[[input]]
name = "test"
dir = "."
driver = "text"
atype = "requirement"
""",
        encoding='utf-8',
    )
    params = Params(verbose=False, render_tree=False, ai=False)
    config = Config(params=params, config_filename=cfg_path)

    artifacts = {}
    art1 = Artifact(config)
    art1.location = FileLocation('test.txt')
    artifacts['ART-1'] = art1

    populate_revisions(config, artifacts)
    assert len(art1.revisions) == 0
    assert 'Not a git repository, skipping revision extraction.' in caplog.text
