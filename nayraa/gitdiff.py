import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from nayraa.budget import is_excluded


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str
    changed_lines: frozenset[int]


class GitError(Exception):
    pass


def _git_run(args: list[str], repo_root: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(e.stderr) from e


def changed_files(repo_root: Path, base: str, head: str) -> list[ChangedFile]:
    result = _git_run(
        ["git", "-C", str(repo_root), "diff", "--name-status", f"{base}...{head}"],
        repo_root,
    )
    changed = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0][0]
        path = parts[-1]
        if is_excluded(path):
            continue
        if status == "D":
            continue
        diff_result = _git_run(
            [
                "git",
                "-C",
                str(repo_root),
                "diff",
                "--unified=0",
                f"{base}...{head}",
                "--",
                path,
            ],
            repo_root,
        )
        changed_lines = set()
        for match in re.finditer(
            r"@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@",
            diff_result.stdout,
        ):
            start = int(match.group(3))
            count_str = match.group(4)
            count = int(count_str) if count_str else 1
            if count == 0:
                changed_lines.add(max(1, start))
                continue
            for i in range(count):
                changed_lines.add(start + i)
        changed.append(
            ChangedFile(
                path=path, status=status, changed_lines=frozenset(changed_lines)
            )
        )
    return changed


def unified_diff(repo_root: Path, base: str, head: str) -> str:
    changed = changed_files(repo_root, base, head)
    paths = [cf.path for cf in changed]
    if not paths:
        return ""
    result = _git_run(
        ["git", "-C", str(repo_root), "diff", "--unified=3", f"{base}...{head}", "--"]
        + paths,
        repo_root,
    )
    return result.stdout
