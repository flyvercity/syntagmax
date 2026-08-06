from syntagmax.impact import _generate_suspicious_tree
from syntagmax.artifact import Artifact
from syntagmax.config import Config, Params


def test_generate_suspicious_tree_with_updated(tmp_path):
    config_file = tmp_path / 'config.toml'
    config_file.write_text('input = []', encoding='utf-8')
    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True)
    config = Config(params, config_file)

    root = Artifact(config)
    root.aid = 'ROOT'
    root.atype = 'ROOT'
    root.children = {'SYS-001'}

    p = Artifact(config)
    p.aid = 'SYS-001'
    p.atype = 'SYS'
    p.children = {'REQ-001'}

    c = Artifact(config)
    c.aid = 'REQ-001'
    c.atype = 'REQ'
    c.children = set()

    artifacts = {'ROOT': root, 'SYS-001': p, 'REQ-001': c}
    suspicious_aids = {'REQ-001'}
    updated_aids = {'SYS-001'}

    tree = _generate_suspicious_tree(artifacts, suspicious_aids, updated_aids)
    print('\n' + tree)

    assert 'REQ:REQ-001 [!] OUTDATED' in tree
    assert 'SYS:SYS-001 [*] UPDATED' in tree


def test_generate_suspicious_tree_both_marks(tmp_path):
    config_file = tmp_path / 'config.toml'
    config_file.write_text('input = []', encoding='utf-8')
    params = Params(verbose=False, render_tree=False, ai=False, cwd=str(tmp_path), no_git=True)
    config = Config(params, config_file)

    root = Artifact(config)
    root.aid = 'ROOT'
    root.atype = 'ROOT'
    root.children = {'A'}

    a = Artifact(config)
    a.aid = 'A'
    a.atype = 'TYPE'
    a.children = {'B'}

    b = Artifact(config)
    b.aid = 'B'
    b.atype = 'TYPE'
    b.children = set()

    artifacts = {'ROOT': root, 'A': a, 'B': b}

    # A is updated (causing B to be outdated)
    # AND A is outdated (because some parent, say ROOT, was updated - simplified)
    suspicious_aids = {'A', 'B'}
    updated_aids = {'A'}

    tree = _generate_suspicious_tree(artifacts, suspicious_aids, updated_aids)
    print('\n' + tree)

    assert 'TYPE:A [!] OUTDATED [*] UPDATED' in tree
    assert 'TYPE:B [!] OUTDATED' in tree
