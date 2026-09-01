from nayraa.tools import RepoTools


def test_read_file_returns_contents(repo):
    tools = RepoTools(repo.root)
    assert "def helper" in tools.read_file("pkg/a.py")


def test_read_file_refuses_paths_outside_the_repository(repo):
    tools = RepoTools(repo.root)
    assert tools.read_file("../../etc/passwd").startswith("no such file")


def test_read_file_refuses_excluded_paths(repo):
    tools = RepoTools(repo.root)
    assert tools.read_file("pkg/migrations/0001_x.py").startswith("no such file")


def test_read_file_reports_a_missing_file(repo):
    tools = RepoTools(repo.root)
    assert tools.read_file("pkg/nope.py").startswith("no such file")


def test_search_finds_a_symbol(repo):
    tools = RepoTools(repo.root)
    out = tools.search("def helper")
    assert "pkg/a.py" in out


def test_search_reports_no_matches(repo):
    tools = RepoTools(repo.root)
    assert tools.search("zzz_not_present_zzz") == "no matches"


def test_list_dir_lists_names(repo):
    tools = RepoTools(repo.root)
    out = tools.list_dir("pkg")
    assert "a.py" in out
    assert "b.py" in out


def test_list_dir_refuses_escape(repo):
    tools = RepoTools(repo.root)
    assert tools.list_dir("..").startswith("no such directory")


def test_as_callables_exposes_three_tools(repo):
    tools = RepoTools(repo.root)
    names = [c.__name__ for c in tools.as_callables()]
    assert names == ["read_file", "search", "list_dir"]
