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
