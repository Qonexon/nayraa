import ast
from dataclasses import dataclass, field
from pathlib import Path

from nayraa.budget import is_excluded


@dataclass
class ImportGraph:
    imports: dict[str, set[str]] = field(default_factory=dict)
    importers: dict[str, set[str]] = field(default_factory=dict)

    def imports_of(self, path: str) -> set[str]:
        return self.imports.get(path, set())

    def importers_of(self, path: str) -> set[str]:
        return self.importers.get(path, set())


def _resolve_module(
    root: Path, src_roots: list[str], module_parts: list[str]
) -> str | None:
    for src_root in src_roots:
        rel = root / src_root
        for part in module_parts:
            rel = rel / part
        if rel.with_suffix(".py").exists():
            return rel.with_suffix(".py").relative_to(root).as_posix()
        init = rel / "__init__.py"
        if init.exists():
            return init.relative_to(root).as_posix()
    return None


def _record_edge(
    imports: dict[str, set[str]],
    importers: dict[str, set[str]],
    from_path: str,
    to_path: str,
) -> None:
    imports.setdefault(from_path, set()).add(to_path)
    importers.setdefault(to_path, set()).add(from_path)


def build_graph(repo_root: Path, src_roots: list[str]) -> ImportGraph:
    imports: dict[str, set[str]] = {}
    importers: dict[str, set[str]] = {}
    py_files = list(repo_root.rglob("*.py"))
    for py_file in py_files:
        rel_path = py_file.relative_to(repo_root).as_posix()
        if is_excluded(rel_path):
            continue
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except SyntaxError:
            continue
        importing_path = rel_path
        imports.setdefault(importing_path, set())
        file_dir_parts = py_file.parent.relative_to(repo_root).parts
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_parts = alias.name.split(".")
                    resolved = _resolve_module(repo_root, src_roots, mod_parts)
                    if resolved:
                        _record_edge(imports, importers, importing_path, resolved)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    if not node.module:
                        continue
                    base_parts = node.module.split(".")
                else:
                    base_parts = list(file_dir_parts)
                    for _ in range(node.level - 1):
                        if base_parts:
                            base_parts.pop()
                    if node.module:
                        base_parts.extend(node.module.split("."))
                resolved = _resolve_module(repo_root, src_roots, base_parts)
                if resolved:
                    _record_edge(imports, importers, importing_path, resolved)
                for alias in node.names:
                    sub = _resolve_module(
                        repo_root, src_roots, base_parts + [alias.name]
                    )
                    if sub:
                        _record_edge(imports, importers, importing_path, sub)
    return ImportGraph(imports=imports, importers=importers)
