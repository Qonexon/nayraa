import subprocess
from pathlib import Path

from nayraa import budget

MAX_FILE_CHARS = 120_000
MAX_SEARCH_CHARS = 20_000
SEARCH_TIMEOUT = 20


class RepoTools:
    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root.resolve()

    def _resolve(self, path: str) -> Path | None:
        candidate = (self._root / path).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            return None
        if budget.is_excluded(path):
            return None
        return candidate

    def read_file(self, path: str) -> str:
        """Read the full text of a file in the repository.

        Args:
            path: Repository-relative path, for example "nayraa/passes.py".
        """
        resolved = self._resolve(path)
        if resolved is None or not resolved.is_file():
            return f"no such file: {path}"
        try:
            text = resolved.read_text()
        except (UnicodeDecodeError, PermissionError, OSError) as exc:
            return f"could not read {path}: {exc}"
        if len(text) > MAX_FILE_CHARS:
            return text[:MAX_FILE_CHARS] + "\n... truncated"
        return text

    def search(self, pattern: str) -> str:
        """Search the repository for a regular expression, like grep.

        Args:
            pattern: A regular expression, for example "def _grounded_evidence".
        """
        try:
            completed = subprocess.run(
                ["git", "-C", str(self._root), "grep", "-n", "-E", pattern],
                capture_output=True,
                text=True,
                timeout=SEARCH_TIMEOUT,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return f"search failed: {exc}"
        output = completed.stdout
        if not output:
            return "no matches"
        if len(output) > MAX_SEARCH_CHARS:
            return output[:MAX_SEARCH_CHARS] + "\n... truncated"
        return output

    def list_dir(self, path: str) -> str:
        """List the files and directories in a directory of the repository.

        Args:
            path: Repository-relative directory, for example "nayraa".
        """
        resolved = self._resolve(path)
        if resolved is None or not resolved.is_dir():
            return f"no such directory: {path}"
        try:
            names = sorted(child.name for child in resolved.iterdir())
        except (PermissionError, OSError) as exc:
            return f"could not list {path}: {exc}"
        return "\n".join(names) or "empty directory"

    def as_callables(self) -> list:
        return [self.read_file, self.search, self.list_dir]
