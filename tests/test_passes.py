from dataclasses import replace

from nayraa import passes
from nayraa.bundle import Bundle, Section
from nayraa.model import FakeClient
from nayraa.shape import PrShape


def test_low_confidence_dropped_before_refute():
    responses = [
        {
            "findings": [
                {
                    "path": "foo.py",
                    "line": 10,
                    "severity": "blocker",
                    "claim": "low confidence",
                    "failure_scenario": "scenario",
                    "confidence": 0.5,
                }
            ]
        }
    ]
    client = FakeClient(responses)
    b = Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[],
    )
    result = passes.review(client, b, rubric=None)
    assert len(result) == 0
    for call_system, _, _ in client.calls:
        assert "CODEBASE CONVENTIONS" not in call_system


def test_refuted_excluded():
    responses = [
        {
            "findings": [
                {
                    "path": "foo.py",
                    "line": 10,
                    "severity": "blocker",
                    "claim": "real defect",
                    "failure_scenario": "scenario",
                    "confidence": 0.9,
                }
            ]
        },
        {"refuted": True, "reason": "not reachable"},
    ]
    client = FakeClient(responses)
    b = Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[],
    )
    result = passes.review(client, b, rubric=None)
    assert len(result) == 0


def test_truncate_to_three():
    findings = []
    for i in range(5):
        findings.append(
            {
                "path": f"file{i}.py",
                "line": i + 1,
                "severity": "major",
                "claim": f"claim {i}",
                "failure_scenario": "scenario",
                "confidence": 0.9,
            }
        )
    verdict_response = {"refuted": False, "reason": "ok"}
    responses = [{"findings": findings}] + [verdict_response] * 5
    client = FakeClient(responses)
    b = Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[],
    )
    result = passes.review(client, b, rubric=None)
    assert len(result) == 3


def test_high_fanout_beyond_cap():
    findings = []
    for i in range(3):
        findings.append(
            {
                "path": f"file{i}.py",
                "line": i + 1,
                "severity": "blocker",
                "claim": f"claim {i}",
                "failure_scenario": "scenario",
                "confidence": 0.9,
            }
        )
    verdict_response = {"refuted": False, "reason": "ok"}
    responses = [{"findings": findings}] + [verdict_response] * 3
    client = FakeClient(responses)
    b = Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[("foo.py", 50)],
    )
    result = passes.review(client, b, rubric=None)
    assert len(result) == 4
    synthetic = result[3]
    assert synthetic.path == "foo.py"
    assert synthetic.severity == "major"
    assert "high fan-out change" in synthetic.claim
    assert synthetic.confidence == 1.0


def test_rubric_none_no_conventions():
    responses = [
        {"findings": []},
    ]
    client = FakeClient(responses)
    b = Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[],
    )
    passes.review(client, b, rubric=None)
    assert len(client.calls) == 1
    call_system, _, _ = client.calls[0]
    assert "CODEBASE CONVENTIONS" not in call_system


def test_rubric_present_has_conventions():
    responses = [
        {"findings": []},
    ]
    client = FakeClient(responses)
    b = Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[],
    )
    passes.review(client, b, rubric="always use type hints")
    assert len(client.calls) == 1
    call_system, _, _ = client.calls[0]
    assert "CODEBASE CONVENTIONS" in call_system
    assert "always use type hints" in call_system


SHAPE = PrShape(
    files_changed=9,
    added_files=2,
    modified_files=7,
    deleted_files=0,
    lines_added=120,
    lines_removed=14,
    directories=["api", "web"],
    commit_subjects=["add export", "bump timeout"],
    test_files=1,
)


GROUNDED_SHAPE = replace(SHAPE, paths=("api/export.py", "api/client.py"))


def _bundle() -> Bundle:
    return Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[],
    )


def _objection(**overrides) -> dict:
    base = {
        "kind": "mixed_concerns",
        "claim": "adds an export feature and changes the HTTP timeout",
        "evidence": ["api/export.py", "api/client.py"],
        "confidence": 0.8,
    }
    return base | overrides


def test_unjustified_objection_survives():
    client = FakeClient(
        [
            {"objections": [_objection()]},
            {"justified": False, "reason": "the two changes share no code path"},
        ]
    )
    result = passes.review_shape(client, _bundle(), SHAPE)
    assert len(result) == 1
    assert result[0].kind == "mixed_concerns"
    assert result[0].evidence == ("api/export.py", "api/client.py")


def test_justified_objection_dropped():
    client = FakeClient(
        [
            {"objections": [_objection()]},
            {"justified": True, "reason": "export does not run without the timeout"},
        ]
    )
    assert passes.review_shape(client, _bundle(), SHAPE) == []


def test_objection_without_evidence_never_reaches_justify():
    client = FakeClient([{"objections": [_objection(evidence=[])]}])
    assert passes.review_shape(client, _bundle(), SHAPE) == []
    assert len(client.calls) == 1


def test_low_confidence_objection_never_reaches_justify():
    client = FakeClient([{"objections": [_objection(confidence=0.4)]}])
    assert passes.review_shape(client, _bundle(), SHAPE) == []
    assert len(client.calls) == 1


def test_objections_capped_and_ordered_by_confidence(monkeypatch):
    monkeypatch.setattr(passes.budget, "MAX_SHAPE_OBJECTIONS", 2)
    client = FakeClient(
        [
            {
                "objections": [
                    _objection(claim="low", confidence=0.65),
                    _objection(claim="high", confidence=0.95),
                    _objection(claim="mid", confidence=0.8),
                ]
            },
            {"justified": False, "reason": "r"},
            {"justified": False, "reason": "r"},
        ]
    )
    result = passes.review_shape(client, _bundle(), SHAPE)
    assert [o.claim for o in result] == ["high", "mid"]
    assert len(client.calls) == 3


def test_shape_reaches_the_model():
    client = FakeClient([{"objections": []}])
    passes.review_shape(client, _bundle(), SHAPE)
    _, user, _ = client.calls[0]
    assert "pr_shape" in user
    assert "files changed: 9" in user
    assert "bump timeout" in user


def test_evidence_that_is_not_a_changed_path_is_dropped():
    client = FakeClient(
        [{"objections": [_objection(evidence=["unrelated concerns"])]}],
    )
    result = passes.review_shape(client, _bundle(), GROUNDED_SHAPE)
    assert result == []
    assert len(client.calls) == 1


def test_ungrounded_evidence_is_stripped_from_a_real_objection():
    client = FakeClient(
        [
            {"objections": [_objection(evidence=["api/export.py", "vibes"])]},
            {"justified": False, "reason": "r"},
        ]
    )
    result = passes.review_shape(client, _bundle(), GROUNDED_SHAPE)
    assert result[0].evidence == ("api/export.py",)


def test_identical_objections_get_independent_verdicts():
    client = FakeClient(
        [
            {"objections": [_objection(), _objection()]},
            {"justified": True, "reason": "r"},
            {"justified": False, "reason": "r"},
        ]
    )
    result = passes.review_shape(client, _bundle(), GROUNDED_SHAPE)
    assert len(result) == 1
