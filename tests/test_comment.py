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


def test_no_objections_renders_nothing():
    assert comment.render_markdown([], SHAPE) == ""


def test_objection_renders_marker_title_and_evidence():
    objection = ShapeObjection(
        kind="duplicate_mechanism",
        claim="adds a second retry helper alongside http.retry",
        evidence=("api/client.py", "api/retry.py"),
        confidence=0.8,
    )
    body = comment.render_markdown([objection], SHAPE)
    assert body.startswith(comment.MARKER)
    assert "**Duplicate mechanism**" in body
    assert "adds a second retry helper alongside http.retry" in body
    assert "`api/client.py` `api/retry.py`" in body


def test_footer_reports_shape_but_makes_no_size_argument():
    objection = ShapeObjection(
        kind="mixed_concerns",
        claim="claim",
        evidence=("a.py",),
        confidence=0.9,
    )
    body = comment.render_markdown([objection], SHAPE)
    assert "12 files across 2 directories, +420/-31, 2 commits" in body
    assert "never blocks a merge" in body
