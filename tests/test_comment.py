from nayraa import comment
from nayraa.passes import ShapeObjection
from nayraa.shape import PrShape

SHAPE = PrShape(
    files_changed=12,
    added_files=3,
    modified_files=9,
    deleted_files=0,
    lines_added=420,
    lines_removed=31,
    directories=["api", "web"],
    commit_subjects=["one", "two"],
    test_files=2,
)

OBJECTION = ShapeObjection(
    kind="duplicate_mechanism",
    claim="adds a second retry helper alongside http.retry",
    evidence=("api/client.py", "api/retry.py"),
    confidence=0.8,
)


def test_no_objections_says_so_explicitly():
    body = comment.render_markdown([], SHAPE)
    assert body.startswith(comment.MARKER)
    assert "✅ No objection to the shape" in body


def test_failed_lane_is_not_reported_as_an_all_clear():
    body = comment.render_markdown(None, SHAPE)
    assert "No objection" not in body
    assert "could not be run" in body


def test_objection_renders_title_claim_and_evidence():
    body = comment.render_markdown([OBJECTION], SHAPE)
    assert "**Duplicate mechanism**" in body
    assert "adds a second retry helper alongside http.retry" in body
    assert "`api/client.py` `api/retry.py`" in body
    assert "not bugs" in body


def test_footer_reports_shape_and_scope():
    body = comment.render_markdown([], SHAPE)
    assert "12 files across 2 directories, +420/-31, 2 commits" in body
    assert "shape, not correctness" in body
    assert "never blocks a merge" in body


def test_missing_shape_degrades_honestly():
    body = comment.render_markdown([OBJECTION], None)
    assert "**Duplicate mechanism**" in body
    assert "shape could not be computed" in body
