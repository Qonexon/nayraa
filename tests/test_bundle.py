from unittest.mock import patch

from nayraa import bundle
from nayraa.bundle import Section


class MockImportGraph:
    def __init__(self, importers=None, imports=None):
        self._importers = importers or {}
        self._imports = imports or {}

    def importers_of(self, path):
        return self._importers.get(path, set())

    def imports_of(self, path):
        return self._imports.get(path, set())


def test_section_order(repo):
    b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
    assert list(b.parts.keys()) == [
        Section.DIFF,
        Section.CHANGED_FILES,
        Section.IMPORTER_CALL_SITES,
        Section.SIBLINGS,
        Section.IMPORTS,
    ]


def test_render_contains_section_tags(repo):
    b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
    out = b.render()
    assert '<section name="diff">' in out
    assert '<section name="changed_files">' in out
    assert "</section>" in out


def test_changed_files_excluded_migration(repo):
    b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
    paths_in_bundle = b.parts.get(Section.CHANGED_FILES, "")
    assert "pkg/migrations/0001_x.py" not in paths_in_bundle
    assert "pkg/a.py" in paths_in_bundle


def test_degradation_imports_to_signatures_then_drop(repo):
    with patch.object(bundle.budget, "TOKEN_BUDGET", 140):
        b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
        assert b.token_count <= 140
        assert Section.IMPORTS in b.dropped
        assert Section.IMPORTS not in b.parts


def test_degradation_drops_imports_records_dropped(repo):
    with patch.object(bundle.budget, "TOKEN_BUDGET", 50):
        b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
        assert Section.IMPORTS in b.dropped
        assert Section.IMPORTS not in b.parts
        assert Section.SIBLINGS in b.dropped
        assert Section.IMPORTER_CALL_SITES in b.dropped


def test_siblings_outlive_imports(repo):
    with patch.object(bundle.budget, "TOKEN_BUDGET", 10**9):
        full = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
    target = full.token_count - bundle.budget.estimate_tokens(
        full.parts[Section.IMPORTS]
    )
    with patch.object(bundle.budget, "TOKEN_BUDGET", target):
        b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
        assert b.token_count <= target
        assert Section.IMPORTS in b.dropped
        assert Section.SIBLINGS in b.parts
        assert Section.SIBLINGS not in b.dropped


def test_importer_call_sites_populated_for_unchanged_importer(repo):
    with patch.object(bundle.budget, "TOKEN_BUDGET", 10**9):
        b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
    assert Section.IMPORTER_CALL_SITES in b.parts
    assert b.parts[Section.IMPORTER_CALL_SITES].strip()


def test_wrap_files_signatures_strips_bodies():
    src = "def keep_me(a, b):\n    x = a + b\n    return x * 2\n"
    with patch.object(bundle, "_read_text", return_value=src):
        out = bundle._wrap_files(
            __import__("pathlib").Path("/nope"), ["pkg/util.py"], signatures=True
        )
    assert "def keep_me(a, b):" in out
    assert "pass" in out
    assert "x = a + b" not in out
    assert "x * 2" not in out


def test_wrap_files_full_keeps_bodies():
    src = "def keep_me(a, b):\n    x = a + b\n    return x * 2\n"
    with patch.object(bundle, "_read_text", return_value=src):
        out = bundle._wrap_files(
            __import__("pathlib").Path("/nope"), ["pkg/util.py"], signatures=False
        )
    assert "def keep_me(a, b):" in out
    assert "return x * 2" in out


def test_high_fanout_entry_in_bundle_and_no_call_sites(repo):
    mock_graph = MockImportGraph(
        importers={
            "pkg/a.py": {
                "pkg/b.py",
                "pkg/c.py",
                "pkg/d.py",
                "pkg/e.py",
                "pkg/f.py",
            }
        },
        imports={"pkg/b.py": {"pkg/a.py"}},
    )
    with (
        patch.object(bundle.importgraph, "build_graph", return_value=mock_graph),
        patch.object(bundle.budget, "FANOUT_THRESHOLD", 2),
    ):
        b = bundle.build_bundle(repo.root, repo.base, repo.head, ["."])
        assert ("pkg/a.py", 5) in b.high_fanout
        ics = b.parts.get(Section.IMPORTER_CALL_SITES, "")
        assert "pkg/d.py" not in ics
        assert "pkg/e.py" not in ics
        assert "pkg/f.py" not in ics
