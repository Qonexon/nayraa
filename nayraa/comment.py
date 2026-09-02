from nayraa.passes import ShapeObjection
from nayraa.shape import PrShape

MARKER = "<!-- nayraa:shape -->"

KIND_TITLES = {
    "mixed_concerns": "Mixed concerns",
    "duplicate_mechanism": "Duplicate mechanism",
    "unnecessary_complexity": "Unnecessary complexity",
}


def _footer(shape: PrShape | None) -> str:
    if shape is None:
        return (
            "<sub>Pull request shape could not be computed. "
            "nayraa never blocks a merge.</sub>"
        )
    return (
        f"<sub>{shape.files_changed} files across {len(shape.directories)} "
        f"directories, +{shape.lines_added}/-{shape.lines_removed}, "
        f"{len(shape.commit_subjects)} commits. "
        f"nayraa reviews shape, not correctness, and never blocks a merge.</sub>"
    )


def render_markdown(
    objections: list[ShapeObjection] | None, shape: PrShape | None
) -> str:
    blocks = [MARKER, "**nayraa — pull request shape**", ""]

    if objections is None:
        blocks.append("⚠️ Shape review could not be run. See the job log.")
        blocks.append("")
    elif not objections:
        blocks.append("✅ No objection to the shape of this pull request.")
        blocks.append("")
    else:
        blocks.append(
            "These are not bugs. The code may be entirely correct and still be the "
            "wrong shape to merge."
        )
        blocks.append("")
        for objection in objections:
            title = KIND_TITLES.get(objection.kind, objection.kind)
            blocks.append(f"**{title}** — {objection.claim}")
            if objection.evidence:
                blocks.append(" ".join(f"`{path}`" for path in objection.evidence))
            blocks.append("")

    blocks.append("---")
    blocks.append(_footer(shape))
    return "\n".join(blocks) + "\n"
