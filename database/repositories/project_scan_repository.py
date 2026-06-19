from database.models.project_scan_session import ProjectScanSessionModel
from database.session import SessionLocal


def _serialize_scan_session(scan: ProjectScanSessionModel) -> dict:
    return {
        "id": scan.id,
        "owner_user_id": scan.owner_user_id,
        "status": scan.status,
        "filename": scan.filename,
        "file_path": scan.file_path,
        "detected_type": scan.detected_type,
        "project_data": scan.project_data or {},
        "ocr_data": scan.ocr_data or {},
        "detection_data": scan.detection_data or {},
        "confirmed_project_id": scan.confirmed_project_id,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "updated_at": scan.updated_at.isoformat() if scan.updated_at else None,
    }


def create_project_scan_session(
    owner_user_id: str,
    filename: str,
    file_path: str,
    project_data: dict,
    ocr_data: dict,
    detection_data: dict,
) -> dict:
    db = SessionLocal()

    try:
        scan = ProjectScanSessionModel(
            owner_user_id=owner_user_id,
            status="draft",
            filename=filename,
            file_path=file_path,
            detected_type=project_data.get("type"),
            project_data=project_data,
            ocr_data=ocr_data,
            detection_data=detection_data,
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        return _serialize_scan_session(scan)
    finally:
        db.close()


def list_project_scan_sessions(
    owner_user_id: str,
    limit: int = 10,
) -> list[dict]:
    db = SessionLocal()

    try:
        scans = (
            db.query(ProjectScanSessionModel)
            .filter(ProjectScanSessionModel.owner_user_id == owner_user_id)
            .order_by(ProjectScanSessionModel.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [_serialize_scan_session(scan) for scan in scans]
    finally:
        db.close()


def get_project_scan_session(
    scan_id: str,
) -> dict | None:
    db = SessionLocal()

    try:
        scan = (
            db.query(ProjectScanSessionModel)
            .filter(ProjectScanSessionModel.id == scan_id)
            .first()
        )

        if not scan:
            return None

        return _serialize_scan_session(scan)
    finally:
        db.close()


def confirm_project_scan_session(
    scan_id: str,
    owner_user_id: str,
    confirmed_project_id: str | None = None,
) -> dict | None:
    db = SessionLocal()

    try:
        scan = (
            db.query(ProjectScanSessionModel)
            .filter(ProjectScanSessionModel.id == scan_id)
            .filter(ProjectScanSessionModel.owner_user_id == owner_user_id)
            .first()
        )

        if not scan:
            return None

        scan.status = "confirmed"
        scan.confirmed_project_id = confirmed_project_id
        db.commit()
        db.refresh(scan)
        return _serialize_scan_session(scan)
    finally:
        db.close()
