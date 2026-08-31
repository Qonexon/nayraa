from nayraa.passes import Finding, ShapeObjection
from nayraa.shape import PrShape

MARKER = "<!-- nayraa:summary -->"

KIND_TITLES = {
    "mixed_concerns": "Mixed concerns",
    "duplicate_mechanism": "Duplicate mechanism",
    "unnecessary_complexity": "Unnecessary complexity",
}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _defect_block(findings: list[Finding]) -> list[str]:
    if not findings:
        return ["**Code defects** — none", ""]
    blocks = [
        f"**Code defects** — {len(findings)}",
        "",
        "| Severity | Location | Finding |",
        "| --- | --- | --- |",
    ]
    for f in findings:
        blocks.append(f"| {f.severity} | `{f.path}:{f.line}` | {_cell(f.claim)} |")
    blocks.append("")
    blocks.append("Each of these is also posted inline on the line it concerns.")
    blocks.append("")
    return blocks


def _shape_block(objections: list[ShapeObjection] | None) -> list[str]:
    if objections is None:
        return ["**Shape** — could not be reviewed, see the job log", ""]
    if not objections:
        return ["**Shape** — no objections", ""]
    blocks = [f"**Shape** — {len(objections)}", ""]
    for objection in objections:
        title = KIND_TITLES.get(objection.kind, objection.kind)
        blocks.append(f"- **{title}** — {objection.claim}")
        if objection.evidence:
            blocks.append("  " + " ".join(f"`{path}`" for path in objection.evidence))
    blocks.append("")
    blocks.append(
        "Shape objections are not bugs. The code may be entirely correct and still "
        "be the wrong shape to merge."
    )
    blocks.append("")
    return blocks


def render_markdown(
    findings: list[Finding],
    objections: list[ShapeObjection] | None,
    shape: PrShape | None,
) -> str:
    blocks = [MARKER, "**nayraa**", ""]

    if not findings and objections == []:
        blocks.append("✅ **No issues found.** Nothing survived either lane.")
        blocks.append("")
    else:
        blocks.extend(_defect_block(findings))
        blocks.extend(_shape_block(objections))

    blocks.append("---")
    if shape is None:
        blocks.append(
            "<sub>Pull request shape could not be computed. "
            "nayraa never blocks a merge.</sub>"
        )
    else:
        blocks.append(
            f"<sub>{shape.files_changed} files across {len(shape.directories)} "
            f"directories, +{shape.lines_added}/-{shape.lines_removed}, "
            f"{len(shape.commit_subjects)} commits. "
            f"nayraa never blocks a merge.</sub>"
        )
    return "\n".join(blocks) + "\n"
