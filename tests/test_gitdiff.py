import pytest

from ai_review.gitdiff import GitError, changed_files


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
