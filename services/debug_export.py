import json

from pathlib import Path


def export_debug_bom(
    project_id: str | int,
    project: dict
):
    project_id = str(project_id)

    export_dir = Path(
        "exports"
    )

    export_dir.mkdir(
        exist_ok=True
    )

    filepath = (
        export_dir
        / f"{project_id}_bom.json"
    )

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            project,
            f,
            ensure_ascii=False,
            indent=2
        )

    return filepath