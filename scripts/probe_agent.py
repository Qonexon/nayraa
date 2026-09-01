import argparse
import os
import subprocess
import sys
from pathlib import Path

from google import genai
from google.genai import types

from nayraa import gitdiff, passes

ROOT = Path(".").resolve()


def _safe(path: str) -> Path | None:
    p = (ROOT / path).resolve()
    if ROOT not in p.parents and p != ROOT:
        return None
    return p


def read_file(path: str) -> str:
    """Read the full text of a file in the repository.

    Args:
        path: Repository-relative path, e.g. "nayraa/passes.py".
    """
    p = _safe(path)
    if p is None or not p.is_file():
        return f"ERROR: no such file: {path}"
    try:
        return p.read_text()[:120_000]
    except (UnicodeDecodeError, PermissionError) as exc:
        return f"ERROR: {exc}"


def search(pattern: str) -> str:
    """Search the repository for a regular expression, like grep.

    Args:
        pattern: A regular expression, e.g. "def _grounded_evidence".
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "grep", "-n", "-E", pattern],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
    except subprocess.SubprocessError as exc:
        return f"ERROR: {exc}"
    return out[:20_000] or "no matches"


def list_dir(path: str) -> str:
    """List the files in a directory of the repository.

    Args:
        path: Repository-relative directory, e.g. "nayraa".
    """
    p = _safe(path)
    if p is None or not p.is_dir():
        return f"ERROR: no such directory: {path}"
    return "\n".join(sorted(c.name for c in p.iterdir()))


AGENT_SUFFIX = """

You have tools: read_file, search, list_dir. The diff below shows what changed,
but NOT the full contents of the files. Use the tools to read any file you need,
to find callers of a changed function, and to check how a changed value is used
elsewhere. Investigate before you conclude. When you are done, write your findings
as prose: for each one give the file path, the line number, the severity
(blocker or major), the claim, and the concrete failure scenario.
"""

FORMAT_PROMPT = """You convert a code review written as prose into JSON.
Copy the findings faithfully. Do not add findings. Do not drop findings.
If the review states there are no findings, return an empty array."""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--model", default=os.environ.get("AI_REVIEW_MODEL", "gemini-3.7-flash"))
    ap.add_argument("--max-calls", type=int, default=40)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--prompt", default="baseline", choices=["baseline", "v5"])
    ap.add_argument("--show-prose", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 1

    diff = gitdiff.unified_diff(ROOT, args.base, args.head)
    print(f"diff: {len(diff)} chars", file=sys.stderr, flush=True)

    base_prompt = passes.SYSTEM_PROMPT_FINDINGS
    if args.prompt == "v5":
        base_prompt = base_prompt.replace(
            "Report only defects that would make you block the merge.",
            "You are the first of two reviewers. Your job is to PROPOSE candidate "
            "defects. A second reviewer will try to refute each one, so a candidate "
            "that turns out to be wrong costs nothing. Failing to propose a real "
            "defect is the only unrecoverable error.",
        ).replace(
            "Report at most 8 findings. Fewer is better. Zero is a valid and common answer.",
            "Report at most 8 findings.",
        )

    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=base_prompt + AGENT_SUFFIX,
        tools=[read_file, search, list_dir],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=args.max_calls
        ),
    )

    for run in range(args.repeat):
        response = client.models.generate_content(
            model=args.model, contents=diff, config=config
        )
        prose = response.text or ""
        calls = len(response.automatic_function_calling_history or [])
        print(f"\n=== run {run}: {calls} tool messages ===", flush=True)
        if args.show_prose:
            print(f"--- prose ---\n{prose[:4000]}\n--- end ---", flush=True)

        structured = client.models.generate_content(
            model=args.model,
            contents=prose,
            config=types.GenerateContentConfig(
                system_instruction=FORMAT_PROMPT,
                response_mime_type="application/json",
                response_json_schema=passes.FINDINGS_SCHEMA,
            ),
        )
        import json

        findings = json.loads(structured.text or "{}").get("findings", [])
        print(f"candidates: {len(findings)}", flush=True)
        for f in findings:
            print(
                f"  [{f.get('confidence')}] {f.get('severity')} "
                f"{f.get('path')}:{f.get('line')}  {f.get('claim')}",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
