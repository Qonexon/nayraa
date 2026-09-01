import json

import pytest

from nayraa import finder


def _comment(**overrides) -> dict:
    base = {
        "path": "api/client.py",
        "content": "retry loop reuses a consumed response body",
        "start_line": 42,
        "end_line": 44,
        "category": "bug",
        "severity": "high",
        "thinking": "the second attempt reads an exhausted stream",
    }
    return base | overrides


def test_parses_ocr_comments():
    payload = json.dumps({"comments": [_comment()]})
    findings = finder.parse(payload)
    assert len(findings) == 1
    f = findings[0]
    assert f.path == "api/client.py"
    assert f.line == 42
    assert f.severity == "blocker"
    assert f.claim == "retry loop reuses a consumed response body"
    assert f.failure_scenario == "the second attempt reads an exhausted stream"


def test_parses_a_bare_array():
    assert len(finder.parse(json.dumps([_comment()]))) == 1


def test_severity_maps_to_two_values():
    payload = json.dumps(
        {
            "comments": [
                _comment(severity="critical", path="a.py"),
                _comment(severity="high", path="b.py"),
                _comment(severity="medium", path="c.py"),
            ]
        }
    )
    assert [f.severity for f in finder.parse(payload)] == [
        "blocker",
        "blocker",
        "major",
    ]


def test_low_severity_is_dropped():
    assert finder.parse(json.dumps({"comments": [_comment(severity="low")]})) == []


def test_out_of_scope_categories_are_dropped():
    for category in ("style", "documentation", "test", "maintainability"):
        payload = json.dumps({"comments": [_comment(category=category)]})
        assert finder.parse(payload) == [], category


def test_excluded_paths_are_dropped():
    payload = json.dumps({"comments": [_comment(path="pkg/migrations/0001_x.py")]})
    assert finder.parse(payload) == []


def test_findings_are_capped(monkeypatch):
    monkeypatch.setattr(finder.budget, "MAX_FINAL_FINDINGS", 2)
    payload = json.dumps({"comments": [_comment(path=f"f{i}.py") for i in range(5)]})
    assert len(finder.parse(payload)) == 2


def test_blockers_sort_first():
    payload = json.dumps(
        {
            "comments": [
                _comment(severity="medium", path="a.py"),
                _comment(severity="critical", path="z.py"),
            ]
        }
    )
    assert [f.path for f in finder.parse(payload)] == ["z.py", "a.py"]


def test_missing_line_defaults_to_one():
    payload = json.dumps({"comments": [_comment(start_line=None)]})
    assert finder.parse(payload)[0].line == 1


def test_empty_claim_is_dropped():
    assert finder.parse(json.dumps({"comments": [_comment(content="  ")]})) == []


def test_non_json_raises():
    with pytest.raises(finder.EngineError):
        finder.parse("ocr: command failed")


def test_unrecognised_payload_yields_nothing():
    assert finder.parse(json.dumps({"summary": "all good"})) == []


def test_ocr_command_is_templated():
    argv = finder._engine_command("ocr", "abc", "def")
    assert argv[0] == "ocr"
    assert "--from" in argv and "abc" in argv
    assert "--to" in argv and "def" in argv
    assert "json" in argv


def test_custom_engine_command_is_templated():
    argv = finder._engine_command("mytool --a {base} --b {head}", "x", "y")
    assert argv == ["mytool", "--a", "x", "--b", "y"]


def test_missing_engine_raises(tmp_path):
    with pytest.raises(finder.EngineError, match="not installed"):
        finder.run(tmp_path, "a", "b", "nayraa-no-such-binary-xyz")
