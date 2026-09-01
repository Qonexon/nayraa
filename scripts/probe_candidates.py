import argparse
import os
import sys
from pathlib import Path

from nayraa import passes
from nayraa.bundle import build_bundle
from nayraa.model import GeminiClient
from nayraa.tools import RepoTools


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--src-root", action="append", default=[])
    parser.add_argument("--tools", action="store_true")
    parser.add_argument("--model", default=os.environ.get("AI_REVIEW_MODEL", "gemini-3.7-flash"))
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
    bundle = build_bundle(
        args.repo_root, args.base, args.head, args.src_root or ["."]
    )
    print(f"bundle: {bundle.token_count} tokens, dropped={bundle.dropped}", file=sys.stderr)

    tools = RepoTools(args.repo_root) if args.tools else None
    candidates = passes.find_candidates(client, bundle, rubric=None, tools=tools)
    print(f"\n=== candidates: {len(candidates)} ===")
    for c in candidates:
        print(f"[{c.confidence:.2f}] {c.severity:8} {c.path}:{c.line}")
        print(f"        {c.claim}")
        print(f"        -> {c.failure_scenario}")


if __name__ == "__main__":
    main()
