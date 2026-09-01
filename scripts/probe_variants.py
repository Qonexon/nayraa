import argparse
import os
import sys
from pathlib import Path

from nayraa import passes
from nayraa.bundle import build_bundle
from nayraa.model import GeminiClient

BASE = passes.SYSTEM_PROMPT_FINDINGS

ZERO_PERMISSION = (
    "Report at most 8 findings. Fewer is better. Zero is a valid and common answer.\n"
)

BLOCK_ONLY = (
    "Report only defects that would make you block the merge. "
    "A defect is something that\n"
    "produces wrong behaviour, data loss, a crash, or a security hole.\n"
)

PROPOSAL = (
    "Propose candidate defects for adversarial review. "
    "A second reviewer will independently\n"
    "try to refute every candidate you produce, and anything it can refute is "
    "discarded before\n"
    "a human sees it. Proposing a candidate that later turns out to be wrong "
    "costs nothing.\n"
    "Failing to propose a real defect is the only unrecoverable error.\n"
    "\n"
    "A defect is something that produces wrong behaviour, data loss, a crash, "
    "or a security hole.\n"
)

LOOK_FOR = (
    "\n"
    "Look specifically for:\n"
    "- string and collection operations that do not do what their name suggests\n"
    "- inverted conditions, wrong comparison operators, off-by-one boundaries\n"
    "- error paths that swallow a failure and continue as though it succeeded\n"
    "- state that is written on one path and read on another that never sets it\n"
    "- values that are validated in one place and used unvalidated in another\n"
    "- concurrency: shared state mutated from more than one task\n"
)

CAP_ONLY = "Report at most 8 findings.\n"


def variants() -> dict[str, str]:
    v = {"baseline": BASE}
    v["v1_no_zero_permission"] = BASE.replace(ZERO_PERMISSION, CAP_ONLY)
    v["v2_proposal_framing"] = BASE.replace(BLOCK_ONLY, PROPOSAL)
    v["v3_look_for"] = BASE.replace(ZERO_PERMISSION, CAP_ONLY + LOOK_FOR)
    v["v4_all"] = BASE.replace(BLOCK_ONLY, PROPOSAL).replace(
        ZERO_PERMISSION, CAP_ONLY + LOOK_FOR
    )
    v["v5_proposal_no_lookfor"] = BASE.replace(BLOCK_ONLY, PROPOSAL).replace(
        ZERO_PERMISSION, CAP_ONLY
    )
    v["v6_proposal_plus_lookfor_keep_zero"] = BASE.replace(
        BLOCK_ONLY, PROPOSAL
    ).replace(ZERO_PERMISSION, ZERO_PERMISSION + LOOK_FOR)
    v["think_baseline"] = BASE
    v["think_v5"] = v["v5_proposal_no_lookfor"]
    return v


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--src-root", action="append", default=[])
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--union", type=int, default=0)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument(
        "--model", default=os.environ.get("AI_REVIEW_MODEL", "gemini-3.7-flash")
    )
    args = parser.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        key_file = Path.home() / ".config" / "nayraa" / "gemini-key"
        if key_file.exists():
            key = key_file.read_text().strip()
    if not key:
        print("no GEMINI_API_KEY", file=sys.stderr)
        raise SystemExit(1)

    client = GeminiClient(api_key=key, model=args.model)
    bundle = build_bundle(args.repo_root, args.base, args.head, args.src_root or ["."])
    print(f"bundle: {bundle.token_count} tokens", file=sys.stderr)

    chosen = variants()
    if args.only:
        chosen = {k: v for k, v in chosen.items() if k in args.only}

    think_schema = {
        "type": "object",
        "required": ["analysis", "findings"],
        "properties": {
            "analysis": {"type": "string"},
            "findings": passes.FINDINGS_SCHEMA["properties"]["findings"],
        },
    }

    def apply(name, prompt):
        if name.startswith("think_"):
            passes.FINDINGS_SCHEMA = think_schema
        passes.SYSTEM_PROMPT_FINDINGS = prompt

    if args.union:
        for name, prompt in chosen.items():
            print(f"\n=== {name}: union of {args.union}, {args.trials} trials ===")
            for trial in range(args.trials):
                seen = {}
                for _ in range(args.union):
                    original = passes.SYSTEM_PROMPT_FINDINGS
                    passes.SYSTEM_PROMPT_FINDINGS = prompt
                    try:
                        cands = passes.find_candidates(client, bundle, rubric=None)
                    except Exception as exc:
                        print(f"  ERROR {exc}", flush=True)
                        cands = []
                    finally:
                        passes.SYSTEM_PROMPT_FINDINGS = original
                    for c in cands:
                        seen.setdefault(c.path, []).append(c.claim[:70])
                print(f"  trial {trial}: {len(seen)} distinct files", flush=True)
                for path, claims in seen.items():
                    print(f"    {path} (x{len(claims)}) {claims[0]}", flush=True)
        return

    for name, prompt in chosen.items():
        counts = []
        hits = []
        for _ in range(args.repeat):
            original = passes.SYSTEM_PROMPT_FINDINGS
            original_schema = passes.FINDINGS_SCHEMA
            apply(name, prompt)
            try:
                candidates = passes.find_candidates(client, bundle, rubric=None)
            except Exception as exc:
                print(f"{name}: ERROR {exc}", flush=True)
                continue
            finally:
                passes.SYSTEM_PROMPT_FINDINGS = original
                passes.FINDINGS_SCHEMA = original_schema
            counts.append(len(candidates))
            for c in candidates:
                hits.append(f"{c.path}:{c.line} [{c.confidence:.2f}] {c.claim[:90]}")
        runs = len(counts)
        nonzero = sum(1 for c in counts if c > 0)
        total = sum(counts)
        print(
            f"\n=== {name}: {nonzero}/{runs} runs found something, "
            f"{total} candidates total, counts={counts} ===",
            flush=True,
        )
        for h in hits:
            print(f"  {h}", flush=True)


if __name__ == "__main__":
    main()
