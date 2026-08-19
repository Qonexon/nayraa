import json

from ai_review import rdjson
from ai_review.passes import Finding


def test_clamp_nearest_line():
    f = Finding(
        path="foo.py",
        line=50,
        severity="major",
        claim="test claim",
        failure_scenario="test scenario",
        confidence=0.8,
    )
    changed = {"foo.py": frozenset([10, 20, 30])}
    result = rdjson.clamp_to_diff_lines(f, changed)
    assert result.line == 30
    assert "(reported near line 50)" in result.claim
    assert result.claim == "(reported near line 50) test claim"


def test_clamp_path_missing():
    f = Finding(
        path="bar.py",
        line=50,
        severity="blocker",
        claim="test claim",
        failure_scenario="test scenario",
        confidence=0.8,
    )
    changed: dict[str, frozenset[int]] = {}
    result = rdjson.clamp_to_diff_lines(f, changed)
    assert result.line == 1


def test_clamp_path_empty_set():
    f = Finding(
        path="bar.py",
        line=50,
        severity="blocker",
        claim="test claim",
        failure_scenario="test scenario",
        confidence=0.8,
    )
    changed = {"bar.py": frozenset()}
    result = rdjson.clamp_to_diff_lines(f, changed)
    assert result.line == 1


def test_clamp_line_in_changed():
    f = Finding(
        path="foo.py",
        line=20,
        severity="blocker",
        claim="test claim",
        failure_scenario="test scenario",
        confidence=0.8,
    )
    changed = {"foo.py": frozenset([10, 20, 30])}
    result = rdjson.clamp_to_diff_lines(f, changed)
    assert result.line == 20
    assert result.claim == "test claim"


def test_blocker_maps_to_error():
    f = Finding(
        path="foo.py",
        line=10,
        severity="blocker",
        claim="test claim",
        failure_scenario="test scenario",
        confidence=0.8,
    )
    output = rdjson.to_rdjsonl([f])
    obj = json.loads(output.split("\n")[0])
    assert obj["severity"] == "ERROR"
    assert obj["code"]["value"] == "blocker"


def test_major_maps_to_warning():
    f = Finding(
        path="foo.py",
        line=10,
        severity="major",
        claim="test claim",
        failure_scenario="test scenario",
        confidence=0.8,
    )
    output = rdjson.to_rdjsonl([f])
    obj = json.loads(output.split("\n")[0])
    assert obj["severity"] == "WARNING"
    assert obj["code"]["value"] == "major"


def test_one_json_object_per_line():
    findings = [
        Finding(
            path="foo.py",
            line=10,
            severity="blocker",
            claim="claim 1",
            failure_scenario="scenario 1",
            confidence=0.8,
        ),
        Finding(
            path="bar.py",
            line=20,
            severity="major",
            claim="claim 2",
            failure_scenario="scenario 2",
            confidence=0.9,
        ),
    ]
    output = rdjson.to_rdjsonl(findings)
    lines = output.rstrip("\n").split("\n")
    assert len(lines) == 2
    for line in lines:
        json.loads(line)
