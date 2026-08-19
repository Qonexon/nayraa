import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from nayraa.model import GeminiClient, VertexClient


def _make_repo(tmp: Path) -> tuple[str, str]:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.email", "t@e"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
    (tmp / "pkg").mkdir()
    (tmp / "pkg" / "__init__.py").write_text("")
    (tmp / "pkg" / "a.py").write_text("def helper(x):\n    return x + 1\n")
    (tmp / "pkg" / "b.py").write_text(
        "from pkg.a import helper\n\ndef other():\n    return helper(1)\n"
    )
    subprocess.run(["git", "add", "."], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    (tmp / "pkg" / "a.py").write_text(
        "def helper(x, y=None):\n    return x + (y or 0)\n"
    )
    subprocess.run(["git", "add", "."], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "change"], cwd=tmp, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    return base, head


FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "line": {"type": "integer"},
                    "severity": {"type": "string", "enum": ["blocker", "major"]},
                    "claim": {"type": "string"},
                    "failure_scenario": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "path",
                    "line",
                    "severity",
                    "claim",
                    "failure_scenario",
                    "confidence",
                ],
            },
        }
    },
    "required": ["findings"],
}


def main() -> int:
    backend = os.environ.get("AI_REVIEW_BACKEND", "gemini")
    if backend == "vertex":
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            print(
                "GOOGLE_CLOUD_PROJECT not set; skipping live API smoke", file=sys.stderr
            )
            return 0
        client: object = VertexClient(
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            model=os.environ.get("AI_REVIEW_MODEL", "gemini-2.5-flash"),
        )
    else:
        if not os.environ.get("GEMINI_API_KEY"):
            print("GEMINI_API_KEY not set; skipping live API smoke", file=sys.stderr)
            return 0
        client = GeminiClient(
            api_key=os.environ["GEMINI_API_KEY"],
            model=os.environ.get("AI_REVIEW_MODEL", "gemini-2.5-flash"),
        )

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        base, head = _make_repo(tmp)
        from nayraa import bundle as B

        b = B.build_bundle(tmp, base, head, ["."])
        system = "Return zero findings as JSON conforming to the schema."
        user = b.render()
        result = client.complete_json(system, user, FINDINGS_SCHEMA)
        assert isinstance(result, dict), f"expected dict, got {type(result)}"
        assert "findings" in result, f"missing 'findings' key: {list(result)}"
        assert isinstance(result["findings"], list), "findings must be a list"
        for f in result["findings"]:
            assert set(f.keys()) >= {
                "path",
                "line",
                "severity",
                "claim",
                "failure_scenario",
                "confidence",
            }, f"missing keys: {f}"
            assert f["severity"] in {"blocker", "major"}
        print(
            json.dumps(
                {"ok": True, "backend": backend, "findings": len(result["findings"])}
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
