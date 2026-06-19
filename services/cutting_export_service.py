from services.project_cutting_service import (
    build_project_cutting
)


SUPPORTED_CUTTING_EXPORT_FORMATS = [
    {
        "format": "json",
        "label": "Normalized JSON",
        "status": "available",
        "description": "Stable internal cutting export contract"
    },
    {
        "format": "viyar",
        "label": "Viyar",
        "status": "planned",
        "description": "Reserved for Viyar cutting import mapping"
    },
    {
        "format": "giblab",
        "label": "GibLab",
        "status": "planned",
        "description": "Reserved for GibLab cutting import mapping"
    }
]


def list_cutting_export_formats():

    return SUPPORTED_CUTTING_EXPORT_FORMATS


def build_cutting_json_export(project):

    cutting = build_project_cutting(
        project
    )

    return {
        "format": "json",
        "version": "1.0",
        "project": {
            "id": project.id,
            "name": project.project_name,
            "type": project.project_type,
            "client": project.client_name,
            "room": project.room_name,
            "width": project.width,
            "height": project.height,
            "depth": project.depth,
            "sections": project.sections,
            "drawers": project.drawers,
            "material_thickness": project.material_thickness,
            "facade_thickness": project.facade_thickness,
            "inside_thickness": project.inside_thickness,
            "facade_edge_banding": project.facade_edge_banding,
            "inside_edge_banding": project.inside_edge_banding,
        },
        "cutting": {
            "items": cutting["items"],
            "summary": cutting["summary"]
        },
        "export_targets": [
            "viyar",
            "giblab"
        ]
    }
