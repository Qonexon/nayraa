from ai_review.callsites import (
    changed_symbols,
    find_call_sites,
    siblings_of,
    signatures_only,
)
from ai_review.gitdiff import unified_diff


def test_changed_symbols_finds_helper(repo):
    diff = unified_diff(repo.root, repo.base, repo.head)
    symbols = changed_symbols(diff)
    assert "helper" in symbols


def test_find_call_sites_returns_merged_snippet(repo):
    diff = unified_diff(repo.root, repo.base, repo.head)
    symbols = changed_symbols(diff)
    candidates = {"pkg/b.py"}
    snippets = find_call_sites(repo.root, symbols, candidates)
    assert len(snippets) == 1


def test_two_call_sites_five_lines_apart_merge(repo):
    diff = unified_diff(repo.root, repo.base, repo.head)
    symbols = changed_symbols(diff)
    candidates = {"pkg/b.py"}
    snippets = find_call_sites(repo.root, symbols, candidates)
    assert len(snippets) == 1
    snippet = snippets[0]
    assert snippet.path == "pkg/b.py"
    assert snippet.start_line <= snippet.end_line


def test_signatures_only_replaces_body_with_pass(repo):
    source = (
        "def foo(x, y):\n"
        "    return x + y\n\n\n"
        "class Bar:\n"
        "    def method(self):\n"
        "        pass\n"
    )
    result = signatures_only(source)
    assert "pass" in result
    assert "return" not in result


def test_signatures_only_syntax_error_returns_unchanged(repo):
    source = "def broken(\n"
    result = signatures_only(source)
    assert result == source


def test_siblings_of(repo):
    siblings = siblings_of(repo.root, "pkg/a.py", limit=2)
    assert len(siblings) == 2
    assert "pkg/a.py" not in siblings
    assert all(s.startswith("pkg/") and s.endswith(".py") for s in siblings)


def test_end_line_at_eof(repo):
    pkg_b = repo.root / "pkg" / "b.py"
    original = pkg_b.read_text()
    near_eof = "\n".join([""] * 20 + ["y = helper(1)"])
    pkg_b.write_text(original + near_eof)
    try:
        symbols = {"helper"}
        candidates = {"pkg/b.py"}
        snippets = find_call_sites(repo.root, symbols, candidates)
        for s in snippets:
            assert s.end_line <= len(s.text.splitlines())
            assert s.text.count("\n") + 1 == s.end_line - s.start_line + 1
    finally:
        pkg_b.write_text(original)
