import json

from ai_review.passes import Finding


def clamp_to_diff_lines(
    finding: Finding, changed: dict[str, frozenset[int]]
) -> Finding:
    path = finding.path
    if path not in changed or not changed[path]:
        return Finding(
            path=finding.path,
            line=1,
            severity=finding.severity,
            claim=finding.claim,
            failure_scenario=finding.failure_scenario,
            confidence=finding.confidence,
        )
    lines = changed[path]
    if finding.line in lines:
        return finding
    original_line = finding.line
    nearest = min(lines, key=lambda ln: abs(ln - original_line))
    return Finding(
        path=finding.path,
        line=nearest,
        severity=finding.severity,
        claim=f"(reported near line {original_line}) {finding.claim}",
        failure_scenario=finding.failure_scenario,
        confidence=finding.confidence,
    )


def to_rdjsonl(findings: list[Finding]) -> str:
    lines = []
    for f in findings:
        if f.severity == "blocker":
            severity = "ERROR"
        else:
            severity = "WARNING"
        obj = {
            "message": f"{f.claim}\n\n{f.failure_scenario}",
            "location": {
                "path": f.path,
                "range": {"start": {"line": f.line, "column": 1}},
            },
            "severity": severity,
            "code": {"value": f.severity},
        }
        lines.append(json.dumps(obj))
    return "\n".join(lines) + "\n"
