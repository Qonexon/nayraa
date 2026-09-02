import argparse
import os
import sys
import traceback
from pathlib import Path

from nayraa import comment, gitdiff, passes, shape
from nayraa.model import GeminiClient


def main() -> None:
    out: Path | None = None
    try:
        out = _out_path()
        _run()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        if out is not None and not out.exists():
            try:
                out.write_text(comment.render_markdown(None, None))
            except OSError:
                traceback.print_exc(file=sys.stderr)


def _out_path() -> Path | None:
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--out" and i + 1 < len(argv):
            return Path(argv[i + 1])
        if arg.startswith("--out="):
            return Path(arg.split("=", 1)[1])
    return None


def _run() -> None:
    parser = argparse.ArgumentParser(prog="nayraa")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        args.out.write_text(comment.render_markdown(None, None))
        return

    model = args.model or os.environ.get("NAYRAA_MODEL") or "gemini-3.5-flash"

    pr_shape: shape.PrShape | None = None
    objections: list[passes.ShapeObjection] | None = None
    try:
        pr_shape = shape.compute(args.repo_root, args.base, args.head)
        print(f"shape: {pr_shape.files_changed} files", file=sys.stderr)
        diff = gitdiff.unified_diff(args.repo_root, args.base, args.head)
        client = GeminiClient(api_key=api_key, model=model)
        objections = passes.review_shape(client, diff, pr_shape)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    args.out.write_text(comment.render_markdown(objections, pr_shape))


if __name__ == "__main__":
    main()
