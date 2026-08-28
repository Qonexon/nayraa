from nayraa import passes
from nayraa.bundle import Bundle, Section
from nayraa.model import FakeClient


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


def test_architectural_blast_radius_finding_upheld():
    responses = [
        {
            "findings": [
                {
                    "path": "api/views/product.py",
                    "line": 180,
                    "severity": "blocker",
                    "claim": (
                        "Granularity mismatch: hiding a single item excludes "
                        "the entire parent channel"
                    ),
                    "failure_scenario": (
                        "Marking one provider product hidden excludes sibling "
                        "products on the same talent channel"
                    ),
                    "confidence": 0.95,
                }
            ]
        },
        {
            "refuted": False,
            "reason": "No guard prevents sibling channel exclusion in query",
        },
    ]
    client = FakeClient(responses)
    b = Bundle(
        parts={Section.DIFF: ""},
        token_count=0,
        dropped=[],
        high_fanout=[],
    )
    result = passes.review(client, b, rubric=None)
    assert len(result) == 1
    assert result[0].path == "api/views/product.py"
    assert result[0].severity == "blocker"
    assert "Granularity mismatch" in result[0].claim
    assert result[0].confidence == 0.95


def test_system_prompt_includes_structural_defect_patterns():
    assert "Granularity and blast-radius mismatches" in passes.SYSTEM_PROMPT_FINDINGS
    assert "Polarity and fail-open inversions" in passes.SYSTEM_PROMPT_FINDINGS
    assert "Precedence and shadowing collisions" in passes.SYSTEM_PROMPT_FINDINGS
    assert "Incomplete state-space expansions" in passes.SYSTEM_PROMPT_FINDINGS
    assert "Edge-only invariant enforcement" in passes.SYSTEM_PROMPT_FINDINGS
    assert "architectural or blast-radius claims" in passes.SYSTEM_PROMPT_VERDICT
