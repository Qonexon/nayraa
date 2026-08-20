import argparse
import os
import sys
import traceback
from pathlib import Path

from nayraa import budget, bundle, passes, rdjson
from nayraa.bundle import build_bundle
from nayraa.model import GeminiClient, ModelClient


def main() -> None:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--repo-root", default=".", type=Path)
        parser.add_argument("--base", required=True)
        parser.add_argument("--head", required=True)
        parser.add_argument("--src-root", action="append", default=[])
        parser.add_argument("--rubric", type=Path)
        parser.add_argument("--model")
        args = parser.parse_args()

        if args.src_root:
            src_roots = args.src_root
        else:
            src_roots = ["."]

        model_name = args.model
        if model_name is None:
            model_name = os.environ.get("AI_REVIEW_MODEL")
        if model_name is None:
            model_name = "gemini-3.7-flash"

        rubric: str | None = None
        if args.rubric is not None:
            rubric_path = args.repo_root / args.rubric
            if rubric_path.exists():
                content = rubric_path.read_text()
                if content.strip():
                    rubric = content
                else:
                    print("rubric file is empty", file=sys.stderr)
                    rubric = None
            else:
                print("rubric file not found", file=sys.stderr)
                rubric = None

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("GEMINI_API_KEY is not set", file=sys.stderr)
            return
        client: ModelClient = GeminiClient(api_key=api_key, model=model_name)

        b = build_bundle(args.repo_root, args.base, args.head, src_roots)

        for section_name, content in b.parts.items():
            token_count = budget.estimate_tokens(content)
            print(f"{section_name.value}: {token_count} tokens", file=sys.stderr)
        print(f"total: {b.token_count} tokens", file=sys.stderr)

        findings = passes.review(client, b, rubric)

        changed: dict[str, frozenset[int]] = {}
        for cf in bundle.gitdiff.changed_files(args.repo_root, args.base, args.head):
            changed[cf.path] = cf.changed_lines

        clamped = [rdjson.clamp_to_diff_lines(f, changed) for f in findings]
        output = rdjson.to_rdjsonl(clamped)
        print(output, end="")
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return


if __name__ == "__main__":
    main()
