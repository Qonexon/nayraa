import subprocess
from pathlib import Path

from nayraa.importgraph import build_graph


def test_importers_of_a_py(repo):
    graph = build_graph(repo.root, ["."])
    assert graph.importers_of("pkg/a.py") == {"pkg/b.py"}


def test_imports_of_b_py(repo):
    graph = build_graph(repo.root, ["."])
    assert graph.imports_of("pkg/b.py") == {"pkg/a.py"}


def test_import_os_produces_no_edge(repo):
    graph = build_graph(repo.root, ["."])
    for _path, targets in graph.imports.items():
        assert "os" not in targets


def test_relative_import_level1(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(
        ["git", "-C", str(repo_root), "init", "-b", "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    pkg = repo_root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("def helper(x):\n    return x + 1\n")
    (pkg / "d.py").write_text("from .a import helper\n")
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    graph = build_graph(repo_root, ["."])
    assert "pkg/d.py" in graph.importers_of("pkg/a.py")


def test_relative_import_level2(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(
        ["git", "-C", str(repo_root), "init", "-b", "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    pkg = repo_root / "pkg"
    sub = pkg / "sub"
    sub.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (sub / "__init__.py").write_text("")
    (pkg / "a.py").write_text("def helper(x):\n    return x + 1\n")
    (sub / "e.py").write_text("from ..a import helper\n")
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    graph = build_graph(repo_root, ["."])
    assert "pkg/sub/e.py" in graph.importers_of("pkg/a.py")


def _pkg(tmp_path, caller_src):
    from nayraa.importgraph import build_graph

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "target.py").write_text("def helper():\n    return 1\n")
    (tmp_path / "pkg" / "caller.py").write_text(caller_src)
    return build_graph(tmp_path, ["."])


def test_import_from_package_resolves_submodule(tmp_path):
    g = _pkg(tmp_path, "from pkg import target\n")
    assert "pkg/target.py" in g.imports_of("pkg/caller.py")
    assert "pkg/caller.py" in g.importers_of("pkg/target.py")


def test_relative_import_without_module(tmp_path):
    g = _pkg(tmp_path, "from . import target\n")
    assert "pkg/target.py" in g.imports_of("pkg/caller.py")


def test_import_from_submodule_still_resolves(tmp_path):
    g = _pkg(tmp_path, "from pkg.target import helper\n")
    assert "pkg/target.py" in g.imports_of("pkg/caller.py")

