import concurrent.futures
import sys
from dataclasses import dataclass, replace
from typing import Literal

from nayraa import budget
from nayraa.bundle import Bundle
from nayraa.model import ModelClient
from nayraa.shape import PrShape


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


ShapeKind = Literal["mixed_concerns", "duplicate_mechanism", "unnecessary_complexity"]


@dataclass(frozen=True)
class ShapeObjection:
    kind: ShapeKind
    claim: str
    evidence: tuple[str, ...]
    confidence: float


@dataclass
class Justification:
    justified: bool
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

SHAPE_SCHEMA: dict = {
    "type": "object",
    "required": ["objections"],
    "properties": {
        "objections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "claim", "evidence", "confidence"],
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "mixed_concerns",
                            "duplicate_mechanism",
                            "unnecessary_complexity",
                        ],
                    },
                    "claim": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
            },
        }
    },
}

JUSTIFY_SCHEMA: dict = {
    "type": "object",
    "required": ["justified", "reason"],
    "properties": {
        "justified": {"type": "boolean"},
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


SYSTEM_PROMPT_SHAPE = (
    "You are reviewing the SHAPE of a pull request, not the correctness of its "
    "code.\n"
    "\n"
    "A separate reviewer already reports bugs. Do not report wrong behaviour, "
    "crashes,\n"
    "data loss, or security holes. The test for whether an objection belongs to "
    "you: would\n"
    "it still stand after every bug in this diff was fixed? "
    "If not, it is not yours.\n"
    "\n"
    "Report only these three kinds of objection:\n"
    "\n"
    "- mixed_concerns: the diff advances two or more unrelated goals that could "
    "each have\n"
    "  shipped separately, without either one waiting on the other.\n"
    "- duplicate_mechanism: the diff adds a second way to do something this "
    "codebase already\n"
    "  does, instead of using the existing way. You must name the existing "
    "mechanism, and it\n"
    "  must be visible in the provided context.\n"
    "- unnecessary_complexity: the diff adds an abstraction, indirection, "
    "configuration flag,\n"
    "  or layer that has exactly one caller and no second caller anywhere in the "
    "context.\n"
    "\n"
    "Size is context, not evidence. Never object because a diff is large, touches "
    "many files,\n"
    "spans many directories, or has many commits. "
    "A thousand-line mechanical rename is a good\n"
    "pull request. A forty-line change that introduces a second source of truth is "
    "not. Argue\n"
    "from concerns and mechanisms. "
    "If your only argument is a number, you have no objection.\n"
    "\n"
    "Do NOT report any of the following:\n"
    "- the diff is missing tests, docs, or a changelog entry\n"
    "- naming, formatting, file placement, or module organisation preferences\n"
    "- code that is merely unfamiliar, verbose, or not how you would have written "
    "it\n"
    "- anything about code the diff did not touch\n"
    "\n"
    "Every objection must name the specific paths that carry it, in evidence. "
    "An objection you\n"
    "cannot tie to paths does not exist. Do not report it.\n"
    "\n"
    "Report at most 3 objections. Fewer is better. "
    "Zero is the common and expected answer for\n"
    "a focused pull request.\n"
    "\n"
    "Set confidence honestly. Use below 0.6 when you are inferring intent you "
    "cannot see."
)


SYSTEM_PROMPT_JUSTIFY = (
    "You are the author of this pull request, answering one objection to its "
    "shape. State the\n"
    "concrete reason the pull request had to take this shape.\n"
    "\n"
    "A justification is concrete only when it points at something in the provided "
    "context:\n"
    "- the parts cannot be separated because one does not compile, run, or pass "
    "without the\n"
    "  other\n"
    "- the apparent duplicate differs from the existing mechanism in a way the "
    "context shows\n"
    "- the new abstraction already has a second caller in the context\n"
    "- the change is mechanical and uniform, so splitting it would leave the "
    "codebase in a\n"
    "  half-migrated state\n"
    "\n"
    "These are NOT justifications:\n"
    "- the changes are related, adjacent, or convenient to ship together\n"
    "- the author was already working in those files\n"
    "- it is only a small amount of extra code\n"
    "- a second caller is planned, likely, or coming in a follow-up\n"
    "- splitting it would be tedious or would take more pull requests\n"
    "\n"
    "This review inverts the usual burden of proof. Uncertainty does not clear the "
    "objection.\n"
    "If you cannot state a concrete necessity from the provided context, set "
    "justified to\n"
    "false and let the objection stand."
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


def assess_shape(
    client: ModelClient, bundle: Bundle, shape: PrShape
) -> list[ShapeObjection]:
    user = f'<section name="pr_shape">\n{shape.render()}\n</section>\n{bundle.render()}'
    result = client.complete_json(SYSTEM_PROMPT_SHAPE, user, SHAPE_SCHEMA)
    objections: list[ShapeObjection] = []
    for o in result.get("objections", []):
        objections.append(
            ShapeObjection(
                kind=o["kind"],
                claim=o["claim"],
                evidence=tuple(o.get("evidence", [])),
                confidence=o["confidence"],
            )
        )
    return objections


def justify(
    client: ModelClient, bundle: Bundle, shape: PrShape, objection: ShapeObjection
) -> Justification:
    user = (
        f"kind: {objection.kind}\n"
        f"claim: {objection.claim}\n"
        f"evidence: {', '.join(objection.evidence)}\n\n"
        f'<section name="pr_shape">\n{shape.render()}\n</section>\n'
        f"{bundle.render()}"
    )
    result = client.complete_json(SYSTEM_PROMPT_JUSTIFY, user, JUSTIFY_SCHEMA)
    return Justification(justified=result["justified"], reason=result["reason"])


def _grounded_evidence(
    evidence: tuple[str, ...], paths: tuple[str, ...]
) -> tuple[str, ...]:
    if not paths:
        return evidence
    known = set(paths)
    return tuple(e for e in evidence if e.removeprefix("./") in known)


def review_shape(
    client: ModelClient, bundle: Bundle, shape: PrShape
) -> list[ShapeObjection]:
    objections = assess_shape(client, bundle, shape)
    print(f"shape_objections: {len(objections)}", file=sys.stderr)
    survivors = []
    for o in objections:
        if o.confidence < budget.MIN_SHAPE_CONFIDENCE:
            continue
        evidence = _grounded_evidence(o.evidence, shape.paths)
        if not evidence:
            continue
        survivors.append(o if evidence == o.evidence else replace(o, evidence=evidence))
    survivors.sort(key=lambda o: -o.confidence)
    survivors = survivors[: budget.MAX_SHAPE_OBJECTIONS]
    print(
        f"shape_dropped_before_justify: {len(objections) - len(survivors)}",
        file=sys.stderr,
    )
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=budget.JUSTIFY_WORKERS
    ) as executor:
        futures = {
            executor.submit(justify, client, bundle, shape, o): i
            for i, o in enumerate(survivors)
        }
        justifications: dict[int, Justification] = {}
        for fut in concurrent.futures.as_completed(futures):
            justifications[futures[fut]] = fut.result()
    kept = [o for i, o in enumerate(survivors) if not justifications[i].justified]
    print(f"shape_justified: {len(survivors) - len(kept)}", file=sys.stderr)
    print(f"shape_reported: {len(kept)}", file=sys.stderr)
    return kept
