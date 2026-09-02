import concurrent.futures
import sys
from dataclasses import dataclass, replace
from typing import Literal

from nayraa import budget
from nayraa.model import ModelClient
from nayraa.shape import PrShape

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
    "Report at most 3 objections.\n"
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


def assess_shape(
    client: ModelClient, diff: str, shape: PrShape
) -> list[ShapeObjection]:
    user = f'<section name="pr_shape">\n{shape.render()}\n</section>\n{diff}'
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
    client: ModelClient, diff: str, shape: PrShape, objection: ShapeObjection
) -> Justification:
    user = (
        f"kind: {objection.kind}\n"
        f"claim: {objection.claim}\n"
        f"evidence: {', '.join(objection.evidence)}\n\n"
        f'<section name="pr_shape">\n{shape.render()}\n</section>\n'
        f"{diff}"
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
    client: ModelClient, diff: str, shape: PrShape
) -> list[ShapeObjection]:
    objections = assess_shape(client, diff, shape)
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
            executor.submit(justify, client, diff, shape, o): i
            for i, o in enumerate(survivors)
        }
        justifications: dict[int, Justification] = {}
        for fut in concurrent.futures.as_completed(futures):
            justifications[futures[fut]] = fut.result()
    kept = [o for i, o in enumerate(survivors) if not justifications[i].justified]
    print(f"shape_justified: {len(survivors) - len(kept)}", file=sys.stderr)
    print(f"shape_reported: {len(kept)}", file=sys.stderr)
    return kept
