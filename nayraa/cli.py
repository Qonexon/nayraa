import argparse
import os
import sys
import traceback
from pathlib import Path

from nayraa import comment, finder, gitdiff, passes, rdjson, shape
from nayraa.model import GeminiClient


def main() -> None:
    try:
        _run()
    except Exception:
        traceback.print_exc(file=sys.stderr)


def _run() -> None:
    parser = argparse.ArgumentParser(prog="nayraa")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--engine", default="ocr")
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--model")
    args = parser.parse_args()

    findings: list[finder.Finding] | None = None
    try:
        findings = finder.run(args.repo_root, args.base, args.head, args.engine)
        print(f"defects: {len(findings)}", file=sys.stderr)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    if findings:
        changed = {
            cf.path: cf.changed_lines
            for cf in gitdiff.changed_files(args.repo_root, args.base, args.head)
        }
        clamped = [rdjson.clamp_to_diff_lines(f, changed) for f in findings]
        print(rdjson.to_rdjsonl(clamped), end="")
    else:
        clamped = []

    if args.summary_out is None:
        return

    pr_shape: shape.PrShape | None = None
    objections: list[passes.ShapeObjection] | None = None

    api_key = os.environ.get("GEMINI_API_KEY", "")
    model_name = args.model or os.environ.get("AI_REVIEW_MODEL") or "gemini-3.7-flash"

    try:
        pr_shape = shape.compute(args.repo_root, args.base, args.head)
        print(f"shape: {pr_shape.files_changed} files", file=sys.stderr)
        if not api_key:
            print("GEMINI_API_KEY is not set, skipping shape lane", file=sys.stderr)
        else:
            client = GeminiClient(api_key, model_name)
            diff = gitdiff.unified_diff(args.repo_root, args.base, args.head)
            objections = passes.review_shape(client, diff, pr_shape)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    args.summary_out.write_text(
        comment.render_markdown(clamped, objections, pr_shape, findings is None)
    )
