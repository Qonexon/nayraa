import ast
import re
from dataclasses import dataclass
from pathlib import Path

from nayraa.budget import CALL_SITE_CONTEXT_LINES, is_excluded


@dataclass(frozen=True)
class Snippet:
    path: str
    start_line: int
    end_line: int
    text: str


def changed_symbols(diff_text: str) -> set[str]:
    symbols: set[str] = set()
    for line in diff_text.splitlines():
        m = re.match(r"^[+-]\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)", line)
        if m:
            name = m.group(1)
            if len(name) >= 3 and not name.startswith("__"):
                symbols.add(name)
            continue
        m = re.match(r"^[+-]\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", line)
        if m:
            name = m.group(1)
            if len(name) >= 3 and not name.startswith("__"):
                symbols.add(name)
            continue
        m = re.match(r"^[+-]([A-Z_][A-Z0-9_]*)\s*[:=]", line)
        if m:
            name = m.group(1)
            if len(name) >= 3 and not name.startswith("__"):
                symbols.add(name)
    return symbols


def find_call_sites(
    repo_root: Path, symbols: set[str], candidates: set[str]
) -> list[Snippet]:
    if not symbols or not candidates:
        return []
    pattern = re.compile(r"\b(" + "|".join(re.escape(s) for s in symbols) + r")\b")
    snippets: list[Snippet] = []
    file_windows: dict[str, tuple[list[tuple[int, int]], list[str]]] = {}
    for path in candidates:
        if is_excluded(path):
            continue
        file_path = repo_root / path
        if not file_path.exists():
            continue
        lines = file_path.read_text().splitlines()
        windows: list[tuple[int, int]] = []
        for i, line in enumerate(lines):
            if pattern.search(line):
                start = max(0, i - CALL_SITE_CONTEXT_LINES)
                end = min(len(lines) - 1, i + CALL_SITE_CONTEXT_LINES)
                windows.append((start, end))
        if windows:
            windows.sort()
            merged: list[tuple[int, int]] = []
            for w in windows:
                if merged and w[0] <= merged[-1][1] + 1:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], w[1]))
                else:
                    merged.append(w)
            file_windows[path] = (merged, lines)
    for path, (windows, lines) in file_windows.items():
        for start, end in windows:
            text = "\n".join(lines[start : end + 1])
            snippets.append(
                Snippet(path=path, start_line=start + 1, end_line=end + 1, text=text)
            )
    return snippets


def signatures_only(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    class SignatureFixer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            node.body = [ast.Pass()]
            return node

        def visit_AsyncFunctionDef(self, node):
            node.body = [ast.Pass()]
            return node

    fixer = SignatureFixer()
    fixer.visit(tree)
    return ast.unparse(tree)


def siblings_of(repo_root: Path, path: str, limit: int = 2) -> list[str]:
    file_path = repo_root / path
    if not file_path.exists():
        return []
    parent = file_path.parent
    suffix = file_path.suffix
    siblings = []
    for sibling in parent.iterdir():
        if sibling == file_path:
            continue
        if not sibling.is_file():
            continue
        if sibling.suffix != suffix:
            continue
        rel = sibling.relative_to(repo_root).as_posix()
        if is_excluded(rel):
            continue
        siblings.append((sibling.stat().st_size, rel))
    siblings.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in siblings[:limit]]
