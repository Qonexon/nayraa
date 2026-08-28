from nayraa.passes import ShapeObjection
from nayraa.shape import PrShape

MARKER = "<!-- nayraa:shape -->"

KIND_TITLES = {
    "mixed_concerns": "Mixed concerns",
    "duplicate_mechanism": "Duplicate mechanism",
    "unnecessary_complexity": "Unnecessary complexity",
}


def render_markdown(objections: list[ShapeObjection], shape: PrShape) -> str:
    if not objections:
        return ""

    blocks = [
        MARKER,
        "**nayraa — pull request shape**",
        "",
        "These are not bugs. The code may be entirely correct and still be the "
        "wrong shape to merge.",
        "",
    ]
    for objection in objections:
        title = KIND_TITLES.get(objection.kind, objection.kind)
        blocks.append(f"**{title}** — {objection.claim}")
        if objection.evidence:
            blocks.append(" ".join(f"`{path}`" for path in objection.evidence))
        blocks.append("")

    blocks.append("---")
    blocks.append(
        f"<sub>{shape.files_changed} files across {len(shape.directories)} "
        f"directories, +{shape.lines_added}/-{shape.lines_removed}, "
        f"{len(shape.commit_subjects)} commits. "
        f"Shape review is advisory and never blocks a merge.</sub>"
    )
    return "\n".join(blocks) + "\n"
