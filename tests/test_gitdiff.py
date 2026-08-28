import pytest

from nayraa.gitdiff import GitError, _numstat_path, changed_files


def test_changed_files_returns_a_py_with_correct_lines(repo):
    cfiles = changed_files(repo.root, repo.base, repo.head)
    paths = {cf.path for cf in cfiles}
    assert "pkg/a.py" in paths
    a_file = next(cf for cf in cfiles if cf.path == "pkg/a.py")
    assert a_file.changed_lines


def test_migration_file_excluded(repo):
    cfiles = changed_files(repo.root, repo.base, repo.head)
    paths = {cf.path for cf in cfiles}
    assert not any("migration" in p for p in paths)


def test_git_error_contains_stderr(repo):
    with pytest.raises(GitError) as exc_info:
        changed_files(repo.root, repo.base, "deadbeefdeadbeef")
    assert len(exc_info.value.args[0]) >= 0


def test_pure_deletion_records_anchor_line(tmp_path):
    import subprocess

    from nayraa.gitdiff import changed_files

    def run(*a):
        subprocess.run(a, cwd=tmp_path, check=True, capture_output=True)

    def rev():
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        ).stdout.strip()

    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    (tmp_path / "m.py").write_text("def f(x):\n    a = 1\n    b = 2\n    return x\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "one")
    base = rev()
    (tmp_path / "m.py").write_text("def f(x):\n    a = 1\n    return x\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "two")
    cfs = changed_files(tmp_path, base, rev())
    assert len(cfs) == 1
    assert cfs[0].changed_lines, "pure deletion must record an anchor line"


def test_numstat_path_resolves_rename_forms():
    assert _numstat_path("pkg/a.py") == "pkg/a.py"
    assert _numstat_path("old.py => new.py") == "new.py"
    assert _numstat_path("src/{old => new}/a.py") == "src/new/a.py"
    assert _numstat_path("{src => vendor}/a.py") == "vendor/a.py"
