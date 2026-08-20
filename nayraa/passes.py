import concurrent.futures
import sys
from dataclasses import dataclass
from typing import Literal

from nayraa import budget
from nayraa.bundle import Bundle
from nayraa.model import ModelClient


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    severity: Literal["blocker", "major"]
    claim: str
    failure_scenario: str
    confidence: float
    synthetic: bool = False


@dataclass
class Verdict:
    refuted: bool
    reason: str


FINDINGS_SCHEMA: dict = {
    "type": "object",
    "required": ["findings"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "path",
                    "line",
                    "severity",
                    "claim",
                    "failure_scenario",
                    "confidence",
                ],
                "properties": {
                    "path": {"type": "string"},
                    "line": {"type": "integer", "minimum": 1},
                    "severity": {"type": "string", "enum": ["blocker", "major"]},
                    "claim": {"type": "string"},
                    "failure_scenario": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
            },
        }
    },
}

VERDICT_SCHEMA: dict = {
    "type": "object",
    "required": ["refuted", "reason"],
    "properties": {
        "refuted": {"type": "boolean"},
        "reason": {"type": "string"},
    },
}


SYSTEM_PROMPT_FINDINGS = (
    "You are a senior engineer reviewing a pull request in this codebase. "
    "You are the last\n"
    "reviewer before merge.\n"
    "\n"
    "Report only defects that would make you block the merge. "
    "A defect is something that\n"
    "produces wrong behaviour, data loss, a crash, or a security hole.\n"
    "\n"
    "The context may include sibling files from the same directory as a changed file. "
    "Treat those\n"
    "siblings as the authoritative statement of local convention: if the changed code "
    "deviates\n"
    "from the pattern they establish, that deviation is a defect worth reporting. "
    "Do not invent\n"
    "conventions that the provided code does not demonstrate.\n"
    "\n"
    "Do NOT report any of the following. Separate tooling already covers them and "
    "reporting\n"
    "them makes your output worthless:\n"
    "- formatting, whitespace, line length, import order\n"
    "- naming preferences, type annotation style\n"
    "- unused variables or imports, dead code\n"
    "- missing tests or test coverage\n"
    '- refactoring suggestions, "consider extracting", "this could be simpler"\n'
    '- anything you would phrase as "consider", "might want to", or "it may be worth"\n'
    "\n"
    "For every finding you must be able to state a concrete failure: specific input "
    "or state,\n"
    "and the specific wrong output, exception, or corrupted data that results. "
    "If you cannot\n"
    "state that concretely, the finding does not exist. Do not report it.\n"
    "\n"
    "Report at most 8 findings. Fewer is better. Zero is a valid and common answer.\n"
    "\n"
    "Set confidence honestly. Use below 0.6 when you are speculating about code you "
    "cannot\n"
    "fully see in the provided context."
)


SYSTEM_PROMPT_VERDICT = (
    "You are refuting a proposed code review finding. "
    "Your job is to find the reason it is\n"
    "wrong, not to confirm it.\n"
    "\n"
    "Work through these in order:\n"
    "1. Is the code path actually reachable, given callers visible in the context?\n"
    "2. Is the claim about a called function, model, or API correct, given its "
    "definition in\n"
    "the context?\n"
    "3. Is the condition already handled elsewhere — a guard, a validator, a default, "
    "a\n"
    "caller-side check?\n"
    "4. Does the finding depend on code that is not in the context? "
    "If so it is speculation.\n"
    "5. Would this fire on the code as it existed before this diff? "
    "If so it is pre-existing\n"
    "and out of scope for this review.\n"
    "\n"
    "If any of these refutes the finding, set refuted to true.\n"
    "\n"
    "Default to refuted true. Only set it false when you can point to specific lines "
    "in the\n"
    "provided context that prove the defect is real and reachable. "
    "Uncertainty means refuted."
)


def find_candidates(
    client: ModelClient, bundle: Bundle, rubric: str | None
) -> list[Finding]:
    system = SYSTEM_PROMPT_FINDINGS
    if rubric is not None:
        system = system + "\n\nCODEBASE CONVENTIONS:\n" + rubric
    user = bundle.render()
    result = client.complete_json(system, user, FINDINGS_SCHEMA)
    findings: list[Finding] = []
    for f in result.get("findings", []):
        findings.append(
            Finding(
                path=f["path"],
                line=f["line"],
                severity=f["severity"],
                claim=f["claim"],
                failure_scenario=f["failure_scenario"],
                confidence=f["confidence"],
            )
        )
    return findings


def refute(client: ModelClient, bundle: Bundle, finding: Finding) -> Verdict:
    system = SYSTEM_PROMPT_VERDICT
    user = (
        f"path: {finding.path}\n"
        f"line: {finding.line}\n"
        f"severity: {finding.severity}\n"
        f"claim: {finding.claim}\n"
        f"failure_scenario: {finding.failure_scenario}\n"
        f"confidence: {finding.confidence}\n\n"
        f"{bundle.render()}"
    )
    result = client.complete_json(system, user, VERDICT_SCHEMA)
    return Verdict(refuted=result["refuted"], reason=result["reason"])


def review(client: ModelClient, bundle: Bundle, rubric: str | None) -> list[Finding]:
    candidates = find_candidates(client, bundle, rubric)
    print(f"candidates: {len(candidates)}", file=sys.stderr)
    if len(candidates) > budget.MAX_CANDIDATE_FINDINGS:
        candidates = candidates[: budget.MAX_CANDIDATE_FINDINGS]
    survivors = [f for f in candidates if f.confidence >= budget.MIN_CONFIDENCE]
    print(
        f"below_confidence: {len(candidates) - len(survivors)}",
        file=sys.stderr,
    )
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=budget.REFUTE_WORKERS
    ) as executor:
        futures = {executor.submit(refute, client, bundle, f): f for f in survivors}
        verdicts: dict[Finding, Verdict] = {}
        for fut in concurrent.futures.as_completed(futures):
            verdicts[futures[fut]] = fut.result()
    kept = [f for f in survivors if not verdicts[f].refuted]
    print(f"refuted: {len(survivors) - len(kept)}", file=sys.stderr)
    kept.sort(key=lambda f: (f.severity != "blocker", -f.confidence))
    final = kept[: budget.MAX_FINAL_FINDINGS]
    for path, n in bundle.high_fanout:
        final.append(
            Finding(
                path=path,
                line=1,
                severity="major",
                claim=(
                    f"high fan-out change: {n} dependents, impact not machine-verified"
                ),
                failure_scenario=(
                    "Callers of this file were not included because dependent count "
                    "exceeded the threshold. Manually verify blast radius."
                ),
                confidence=1.0,
                synthetic=True,
            )
        )
    print(f"reported: {len(final)}", file=sys.stderr)
    return final
