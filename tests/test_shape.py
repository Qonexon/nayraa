from nayraa import shape
from tests.conftest import RepoFixture


def test_compute_counts_files_and_lines(repo: RepoFixture):
    s = shape.compute(repo.root, repo.base, repo.head)
    assert s.files_changed == 1
    assert s.modified_files == 1
    assert s.added_files == 0
    assert s.lines_added > 0
    assert s.directories == ["pkg"]


def test_compute_collects_commit_subjects(repo: RepoFixture):
    s = shape.compute(repo.root, repo.base, repo.head)
    assert s.commit_subjects == ["change helper signature"]


def test_render_reports_shape_without_a_verdict(repo: RepoFixture):
    s = shape.compute(repo.root, repo.base, repo.head)
    rendered = s.render()
    assert "files changed: 1" in rendered
    assert "directories touched: 1 [pkg]" in rendered
    assert "change helper signature" in rendered


def test_directories_are_capped(monkeypatch):
    monkeypatch.setattr(shape.budget, "MAX_SHAPE_DIRECTORIES", 2)
    s = shape.PrShape(
        files_changed=4,
        added_files=4,
        modified_files=0,
        deleted_files=0,
        lines_added=10,
        lines_removed=0,
        directories=["a", "b", "c", "d"],
        commit_subjects=[],
        test_files=0,
    )
    rendered = s.render()
    assert "[a, b, and 2 more]" in rendered


def test_commits_are_capped(monkeypatch):
    monkeypatch.setattr(shape.budget, "MAX_SHAPE_COMMITS", 1)
    s = shape.PrShape(
        files_changed=1,
        added_files=0,
        modified_files=1,
        deleted_files=0,
        lines_added=1,
        lines_removed=1,
        directories=["a"],
        commit_subjects=["first", "second", "third"],
        test_files=0,
    )
    rendered = s.render()
    assert "- first" in rendered
    assert "second" not in rendered
    assert "- and 2 more" in rendered


def test_test_files_detected_by_directory_and_filename():
    assert shape._is_test_path("pkg/tests/thing.py")
    assert shape._is_test_path("pkg/test_thing.py")
    assert shape._is_test_path("web/thing.test.ts")
    assert not shape._is_test_path("pkg/latest_run.py")
    assert not shape._is_test_path("pkg/contest.py")
