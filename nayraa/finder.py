import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from nayraa import budget

OCR_COMMAND = "ocr review --from {base} --to {head} --format json"
ENGINE_TIMEOUT = 900

SEVERITY_MAP: dict[str, Literal["blocker", "major"]] = {
    "critical": "blocker",
    "high": "blocker",
    "medium": "major",
}

REPORTED_CATEGORIES = frozenset(
    {"bug", "security", "performance", "concurrency", "data", "api", "other", ""}
)

ARRAY_KEYS = ("comments", "findings", "results", "items", "data")


class EngineError(Exception):
    pass


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    severity: Literal["blocker", "major"]
    claim: str
    failure_scenario: str
    confidence: float
    synthetic: bool = False


def _engine_command(engine: str, base: str, head: str) -> list[str]:
    template = OCR_COMMAND if engine == "ocr" else engine
    return shlex.split(template.format(base=base, head=head))


def _extract_array(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ARRAY_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _to_finding(raw: dict) -> Finding | None:
    path = raw.get("path") or raw.get("relevant_file") or raw.get("file")
    if not isinstance(path, str) or not path:
        return None
    if budget.is_excluded(path):
        return None

    category = str(raw.get("category") or "").lower()
    if category not in REPORTED_CATEGORIES:
        return None

    severity = SEVERITY_MAP.get(str(raw.get("severity") or "").lower())
    if severity is None:
        return None

    claim = raw.get("content") or raw.get("suggestion_content") or raw.get("message")
    if not isinstance(claim, str) or not claim.strip():
        return None

    line = raw.get("start_line") or raw.get("line") or 1
    if not isinstance(line, int) or line < 1:
        line = 1

    scenario = raw.get("thinking") or raw.get("existing_code") or ""
    if not isinstance(scenario, str):
        scenario = ""

    return Finding(
        path=path,
        line=line,
        severity=severity,
        claim=claim.strip(),
        failure_scenario=scenario.strip(),
        confidence=1.0,
    )


def parse(stdout: str) -> list[Finding]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise EngineError(f"engine did not return JSON: {exc}") from exc
    findings = [f for f in (_to_finding(r) for r in _extract_array(payload)) if f]
    findings.sort(key=lambda f: (f.severity != "blocker", f.path, f.line))
    return findings[: budget.MAX_FINAL_FINDINGS]


def run(repo_root: Path, base: str, head: str, engine: str) -> list[Finding]:
    argv = _engine_command(engine, base, head)
    if not argv:
        raise EngineError("empty engine command")
    try:
        completed = subprocess.run(
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=ENGINE_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise EngineError(f"engine not installed: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError(f"engine timed out after {ENGINE_TIMEOUT}s") from exc
    if completed.returncode != 0 and not completed.stdout.strip():
        raise EngineError(
            f"engine exited {completed.returncode}: "
            f"{completed.stderr.strip()[:400] or 'no output'}"
        )
    return parse(completed.stdout)
