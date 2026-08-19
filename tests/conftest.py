import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class RepoFixture:
    root: Path
    base: str
    head: str


@pytest.fixture
def repo(tmp_path: Path) -> RepoFixture:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(
        ["git", "-C", str(repo_root), "init", "-b", "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    pkg = repo_root / "pkg"
    pkg.mkdir()
    migrations = pkg / "migrations"
    migrations.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("def helper(x):\n    return x + 1\n")
    (pkg / "util.py").write_text("def transform(v):\n    return v * 2\n")
    b_content = (
        "import os\n"
        "from pkg.a import helper\n\n\n"
        "def other():\n"
        "    pass\n\n\n"
        "y = helper(1)\n"
        "z = helper(2)\n"
    )
    (pkg / "b.py").write_text(b_content)
    (pkg / "c.py").write_text("def sibling():\n    return 42\n")
    (migrations / "0001_x.py").write_text("# migration\n")
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    base = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (pkg / "a.py").write_text(
        "from pkg.util import transform\n\n"
        "\n"
        "def helper(x, y=None):\n"
        "    return transform(x) + 1\n"
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "change helper signature"],
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return RepoFixture(root=repo_root, base=base, head=head)
