import subprocess
import sys
from pathlib import Path

from nayraa import comment


def _run(tmp_path, env_extra, repo):
    out = tmp_path / "shape.md"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env.update(env_extra)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "nayraa.cli",
            "--repo-root",
            str(repo),
            "--base",
            "HEAD~1",
            "--head",
            "HEAD",
            "--out",
            str(out),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return out


def test_missing_key_still_writes_a_could_not_run_body(tmp_path, repo):
    out = _run(tmp_path, {}, repo.root)
    assert out.exists()
    body = out.read_text()
    assert body.startswith(comment.MARKER)
    assert "could not be run" in body
    assert "No objection" not in body


def test_bad_revision_still_writes_a_body(tmp_path, repo):
    out = _run(tmp_path, {"GEMINI_API_KEY": "not-a-real-key"}, repo.root)
    assert out.exists()
    assert "No objection" not in out.read_text()
