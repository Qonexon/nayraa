from nayraa import comment
from nayraa.passes import Finding, ShapeObjection
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

FINDING = Finding(
    path="api/client.py",
    line=42,
    severity="blocker",
    claim="retry loop reuses a consumed response body",
    failure_scenario="second attempt sends an empty payload",
    confidence=0.9,
)

OBJECTION = ShapeObjection(
    kind="duplicate_mechanism",
    claim="adds a second retry helper alongside http.retry",
    evidence=("api/client.py", "api/retry.py"),
    confidence=0.8,
)


def test_nothing_found_still_posts_an_explicit_result():
    body = comment.render_markdown([], [], SHAPE)
    assert body.startswith(comment.MARKER)
    assert "✅ **No issues found.** Nothing survived either lane." in body


def test_failed_shape_lane_is_not_reported_as_an_all_clear():
    body = comment.render_markdown([], None, SHAPE)
    assert "No issues found" not in body
    assert "**Shape** — could not be reviewed" in body
    assert "**Code defects** — none" in body


def test_findings_render_as_a_matrix():
    body = comment.render_markdown([FINDING], [], SHAPE)
    assert "**Code defects** — 1" in body
    assert "| Severity | Location | Finding |" in body
    assert (
        "| blocker | `api/client.py:42` | retry loop reuses a consumed response body |"
        in body
    )
    assert "**Shape** — no objections" in body


def test_shape_objections_render_with_evidence():
    body = comment.render_markdown([], [OBJECTION], SHAPE)
    assert "**Code defects** — none" in body
    assert "**Shape** — 1" in body
    assert (
        "**Duplicate mechanism** — adds a second retry helper alongside http.retry"
        in body
    )
    assert "`api/client.py` `api/retry.py`" in body


def test_both_lanes_render_together():
    body = comment.render_markdown([FINDING], [OBJECTION], SHAPE)
    assert "**Code defects** — 1" in body
    assert "**Shape** — 1" in body
    assert "No issues found" not in body


def test_pipes_in_a_claim_do_not_break_the_table():
    finding = Finding(
        path="a.py",
        line=1,
        severity="major",
        claim="uses a | b instead of a or b",
        failure_scenario="s",
        confidence=0.9,
    )
    body = comment.render_markdown([finding], [], SHAPE)
    assert r"uses a \| b instead of a or b" in body


def test_footer_reports_shape():
    body = comment.render_markdown([], [], SHAPE)
    assert "12 files across 2 directories, +420/-31, 2 commits" in body
    assert "never blocks a merge" in body


def test_missing_shape_degrades_honestly():
    body = comment.render_markdown([FINDING], [], None)
    assert "**Code defects** — 1" in body
    assert "shape could not be computed" in body
