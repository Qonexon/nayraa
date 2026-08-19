from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ai_review import budget, callsites, gitdiff, importgraph


class Section(StrEnum):
    DIFF = "diff"
    CHANGED_FILES = "changed_files"
    IMPORTER_CALL_SITES = "importer_call_sites"
    SIBLINGS = "siblings"
    IMPORTS = "imports"


@dataclass
class Bundle:
    parts: dict[Section, str]
    token_count: int
    dropped: list[Section]
    high_fanout: list[tuple[str, int]]

    def render(self) -> str:
        blocks: list[str] = []
        for section in Section:
            content = self.parts.get(section)
            if content is None:
                continue
            blocks.append(f'<section name="{section.value}">')
            blocks.append(content)
            blocks.append("</section>")
        return "\n".join(blocks)


def _read_text(repo_root: Path, rel: str) -> str:
    try:
        return (repo_root / rel).read_text()
    except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError):
        return ""


def _wrap_files(repo_root: Path, paths: list[str], signatures: bool = False) -> str:
    blocks: list[str] = []
    for p in paths:
        text = _read_text(repo_root, p)
        if signatures:
            text = callsites.signatures_only(text)
        blocks.append(f'<file path="{p}">')
        blocks.append(text)
        blocks.append("</file>")
    return "\n".join(blocks)


def _wrap_snippets(snippets: list[callsites.Snippet]) -> str:
    blocks: list[str] = []
    for s in snippets:
        blocks.append(f'<file path="{s.path}" lines="{s.start_line}-{s.end_line}">')
        blocks.append(s.text)
        blocks.append("</file>")
    return "\n".join(blocks)


def build_bundle(repo_root: Path, base: str, head: str, src_roots: list[str]) -> Bundle:
    changed = gitdiff.changed_files(repo_root, base, head)
    diff_text = gitdiff.unified_diff(repo_root, base, head)
    graph = importgraph.build_graph(repo_root, src_roots)
    symbols = callsites.changed_symbols(diff_text)
    python_changed = [cf.path for cf in changed if cf.path.endswith(".py")]
    already: set[str] = {cf.path for cf in changed}

    parts: dict[Section, str] = {}

    diff_block: list[str] = [diff_text]
    parts[Section.DIFF] = diff_block[0]

    cf_blocks: list[str] = []
    for cf in changed:
        start = min(cf.changed_lines) if cf.changed_lines else 1
        end = max(cf.changed_lines) if cf.changed_lines else 1
        cf_blocks.append(f'<file path="{cf.path}" lines="{start}-{end}">')
        cf_blocks.append(_read_text(repo_root, cf.path))
        cf_blocks.append("</file>")
    parts[Section.CHANGED_FILES] = "\n".join(cf_blocks)

    high_fanout: list[tuple[str, int]] = []
    for path in python_changed:
        importers = graph.importers_of(path)
        if len(importers) > budget.FANOUT_THRESHOLD:
            high_fanout.append((path, len(importers)))
            continue

    ics_blocks: list[str] = []
    for path in python_changed:
        importers = graph.importers_of(path)
        if len(importers) > budget.FANOUT_THRESHOLD:
            continue
        candidates = {p for p in importers if p in already}
        if not symbols or not candidates:
            continue
        for snip in callsites.find_call_sites(repo_root, symbols, candidates):
            ics_blocks.append(
                f'<file path="{snip.path}" lines="{snip.start_line}-{snip.end_line}">'
            )
            ics_blocks.append(snip.text)
            ics_blocks.append("</file>")
    parts[Section.IMPORTER_CALL_SITES] = "\n".join(ics_blocks)

    sib_blocks: list[str] = []
    seen_sib: set[str] = set()
    for cf in changed:
        for sib in callsites.siblings_of(repo_root, cf.path, limit=2):
            if sib in seen_sib or sib in already:
                continue
            seen_sib.add(sib)
            sib_blocks.append(f'<file path="{sib}">')
            sib_blocks.append(_read_text(repo_root, sib))
            sib_blocks.append("</file>")
    if sib_blocks:
        parts[Section.SIBLINGS] = "\n".join(sib_blocks)

    imp_paths: list[str] = []
    seen_imp: set[str] = set()
    for path in python_changed:
        for imp in graph.imports_of(path):
            if imp in seen_imp or imp in already:
                continue
            seen_imp.add(imp)
            imp_paths.append(imp)
    if imp_paths:
        parts[Section.IMPORTS] = _wrap_files(repo_root, imp_paths, signatures=False)

    dropped: list[Section] = []
    token_count = sum(budget.estimate_tokens(v) for v in parts.values())

    if token_count > budget.TOKEN_BUDGET and Section.IMPORTS in parts:
        parts[Section.IMPORTS] = _wrap_files(repo_root, imp_paths, signatures=True)
        token_count = sum(budget.estimate_tokens(v) for v in parts.values())

    if token_count > budget.TOKEN_BUDGET and Section.IMPORTS in parts:
        parts.pop(Section.IMPORTS, None)
        dropped.append(Section.IMPORTS)
        token_count = sum(budget.estimate_tokens(v) for v in parts.values())

    if token_count > budget.TOKEN_BUDGET and Section.SIBLINGS in parts:
        parts.pop(Section.SIBLINGS, None)
        dropped.append(Section.SIBLINGS)
        token_count = sum(budget.estimate_tokens(v) for v in parts.values())

    if token_count > budget.TOKEN_BUDGET and Section.IMPORTER_CALL_SITES in parts:
        parts.pop(Section.IMPORTER_CALL_SITES, None)
        dropped.append(Section.IMPORTER_CALL_SITES)
        token_count = sum(budget.estimate_tokens(v) for v in parts.values())

    return Bundle(
        parts=parts,
        token_count=token_count,
        dropped=dropped,
        high_fanout=high_fanout,
    )
