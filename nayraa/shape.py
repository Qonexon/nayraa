from dataclasses import dataclass
from pathlib import Path, PurePath

from nayraa import budget, gitdiff

TEST_NAME_MARKERS = ("_test.", ".test.", "_spec.", ".spec.")
TEST_DIRECTORIES = ("test", "tests", "spec", "specs", "__tests__")


def _is_test_path(path: str) -> bool:
    pp = PurePath(path)
    if any(part in TEST_DIRECTORIES for part in pp.parts[:-1]):
        return True
    if pp.name.startswith("test_"):
        return True
    return any(marker in pp.name for marker in TEST_NAME_MARKERS)


@dataclass(frozen=True)
class PrShape:
    files_changed: int
    added_files: int
    modified_files: int
    deleted_files: int
    lines_added: int
    lines_removed: int
    directories: list[str]
    commit_subjects: list[str]
    test_files: int
    paths: tuple[str, ...] = ()

    def render(self) -> str:
        dirs = self.directories[: budget.MAX_SHAPE_DIRECTORIES]
        extra_dirs = len(self.directories) - len(dirs)
        dir_text = ", ".join(dirs)
        if extra_dirs > 0:
            dir_text = f"{dir_text}, and {extra_dirs} more"

        commits = self.commit_subjects[: budget.MAX_SHAPE_COMMITS]
        extra_commits = len(self.commit_subjects) - len(commits)
        commit_lines = [f"  - {subject}" for subject in commits]
        if extra_commits > 0:
            commit_lines.append(f"  - and {extra_commits} more")

        lines = [
            f"files changed: {self.files_changed} "
            f"({self.added_files} added, {self.modified_files} modified, "
            f"{self.deleted_files} deleted)",
            f"of which test files: {self.test_files}",
            f"lines: +{self.lines_added} -{self.lines_removed}",
            f"directories touched: {len(self.directories)} [{dir_text}]",
            f"commits: {len(self.commit_subjects)}",
        ]
        lines.extend(commit_lines)
        return "\n".join(lines)


def compute(repo_root: Path, base: str, head: str) -> PrShape:
    statuses = gitdiff.file_statuses(repo_root, base, head)
    added = sum(1 for status, _ in statuses if status == "A")
    deleted = sum(1 for status, _ in statuses if status == "D")
    modified = len(statuses) - added - deleted
    lines_added, lines_removed = gitdiff.line_counts(repo_root, base, head)
    directories = sorted({PurePath(path).parent.as_posix() for _, path in statuses})
    return PrShape(
        files_changed=len(statuses),
        added_files=added,
        modified_files=modified,
        deleted_files=deleted,
        lines_added=lines_added,
        lines_removed=lines_removed,
        directories=directories,
        commit_subjects=gitdiff.commit_subjects(repo_root, base, head),
        test_files=sum(1 for _, path in statuses if _is_test_path(path)),
        paths=tuple(path for _, path in statuses),
    )
