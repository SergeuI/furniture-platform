import os

from sqlalchemy import text

from database.base import Base

from database.session import engine

from database.models.project import (
    ProjectModel
)
from database.models.project_version import (
    ProjectVersionModel
)
from database.models.registration_identity import (
    RegistrationChallengeModel,
    RegistrationIdentityModel,
)
from database.models.entitlement_feature import (
    EntitlementFeatureModel,
)
from database.models.plan_entitlement import (
    PlanEntitlementModel,
)
from database.models.project_scan_session import (
    ProjectScanSessionModel
)
from database.models.user import (
    UserModel
)
from database.models.user_change_request import (
    UserChangeRequestModel
)
from database.models.audit_log import (
    AuditLogModel
)
from database.models.catalog_item import (
    CatalogItemModel
)
from database.models.service_catalog_item import (
    ServiceCatalogItemModel
)
from database.models.fitting_hole_service_rule import (
    FittingHoleServiceRuleModel
)
from database.models.service_drilling_rule import (
    ServiceDrillingRuleModel
)
from database.models.material import (
    MaterialModel
)
from database.models.material_price import (
    MaterialPriceModel
)
from database.models.material_edge import (
    MaterialEdgeModel
)
from database.models.material_edge_price import (
    MaterialEdgePriceModel
)
from database.models.material_user_link import (
    MaterialUserLinkModel
)
from database.models.material_import_job import (
    MaterialImportJobModel
)
from database.models.fitting import (
    FittingHolePointModel,
    FittingHoleTemplateModel,
    FittingModel,
    FittingSupplierOfferModel,
    SupplierModel,
)
from database.models.mounting_node import (
    MountingNodeItemModel,
    MountingNodeModel,
    MountingNodeVersionModel,
    MountingNodeTemplateModel,
)
from database.models.mounting_scheme import (
    MountingSchemeModel,
    MountingSchemeNodeModel,
    MountingSchemePlacementRuleModel,
)
from database.models.fitting_image import (
    FittingImageModel,
)
from database.models.user_service_catalog_price import (
    UserServiceCatalogPriceModel
)
from database.repositories.catalog_repository import (
    seed_default_catalog_items
)
from database.repositories.service_catalog_repository import (
    seed_default_viyar_service_catalog
)
from database.repositories.user_repository import (
    get_user_by_email
)
from services.auth_service import (
    create_managed_user
)
from services.legacy_db_config import (
    ensure_unified_legacy_schema,
    migrate_legacy_sqlite_to_unified_db,
)
from scripts.upgrade_mounting_schemes_schema import (
    ensure_mounting_schemes_schema,
)
from scripts.upgrade_fittings_foundation_schema import (
    ensure_fittings_foundation_schema,
)
from scripts.upgrade_fitting_products_schema import (
    ensure_fitting_products_schema,
)
from scripts.upgrade_fitting_taxonomy_schema import (
    ensure_fitting_taxonomy_schema,
)


def _get_column_names(

    connection,

    table_name: str
) -> set[str]:

    rows = connection.exec_driver_sql(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        row[1]
        for row in rows
    }


def _add_column_if_missing(

    connection,

    table_name: str,

    column_name: str,

    column_type: str
):

    column_names = _get_column_names(

        connection,

        table_name
    )

    if column_name in column_names:

        return

    connection.exec_driver_sql(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    )


def _backfill_mounting_node_versions():

    from database.session import SessionLocal
    from services.mounting_node_service import MountingNodeService

    db = SessionLocal()

    try:
        service = MountingNodeService(session=db)
        with db.begin():
            nodes = (
                db.query(MountingNodeModel)
                .order_by(
                    MountingNodeModel.id.asc()
                )
                .all()
            )

            for node in nodes:
                existing_version = (
                    db.query(MountingNodeVersionModel.id)
                    .filter(
                        MountingNodeVersionModel.node_id == node.id
                    )
                    .first()
                )
                if existing_version:
                    continue

                snapshot_node = service.repository.get_node_by_id(node.id) or node
                snapshot = service._serialize_node(  # noqa: SLF001 - migration helper
                    snapshot_node,
                    include_versions=False,
                )
                from fastapi.encoders import jsonable_encoder

                snapshot = jsonable_encoder(snapshot)
                service.repository.create_version(
                    node_id=node.id,
                    node_code=str(node.code or "").strip(),
                    node_name=str(node.name or "").strip(),
                    version_number=1,
                    event_type="create",
                    snapshot=snapshot,
                    created_by_user_id=getattr(node, "created_by_user_id", None),
                )
    finally:
        db.close()


def upgrade_sqlite_schema():

    with engine.begin() as connection:

        project_specification_columns = {
            "project_name": "VARCHAR",
            "project_type": "VARCHAR",
            "client_name": "VARCHAR",
            "room_name": "VARCHAR",
            "facade_material": "VARCHAR",
            "inside_material": "VARCHAR",
            "facade_edge_banding": "VARCHAR",
            "inside_edge_banding": "VARCHAR",
            "edge_banding": "VARCHAR",
            "edge_overrides": "JSON",
            "machining_overrides": "JSON",
            "facade_thickness": "INTEGER",
            "inside_thickness": "INTEGER",
            "material_thickness": "INTEGER",
            "slide_type": "VARCHAR",
            "bottom_type": "VARCHAR",
            "handle_type": "VARCHAR",
            "handle_position": "VARCHAR",
            "notes": "VARCHAR"
        }

        for column_name, column_type in project_specification_columns.items():

            _add_column_if_missing(

                connection,

                "projects",

                column_name,

                column_type
            )

            _add_column_if_missing(

                connection,

                "project_versions",

                column_name,

                column_type
            )

        _add_column_if_missing(

            connection,

            "projects",

            "created_by_user_id",

            "VARCHAR"
        )

        _add_column_if_missing(

            connection,

            "projects",

            "updated_by_user_id",

            "VARCHAR"
        )

        _add_column_if_missing(

            connection,

            "projects",

            "created_at",

            "DATETIME"
        )

        _add_column_if_missing(

            connection,

            "projects",

            "updated_at",

            "DATETIME"
        )

        _add_column_if_missing(

            connection,

            "project_versions",

            "created_at",

            "DATETIME"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_templates",

            "mounting_variant_key",

            "TEXT NOT NULL DEFAULT 'surface_mount'"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_templates",

            "bundle_key",

            "TEXT"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_templates",

            "bundle_name",

            "TEXT"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_templates",

            "bundle_order_index",

            "INTEGER NOT NULL DEFAULT 0"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_points",

            "target_panel",

            "VARCHAR"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_points",

            "target_surface",

            "VARCHAR"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_points",

            "target_side",

            "VARCHAR"
        )

        _add_column_if_missing(

            connection,

            "fitting_hole_points",

            "service_drilling_rule_id",

            "INTEGER"
        )

        mounting_node_columns = {
            "category_code": "VARCHAR",
            "functional_code": "VARCHAR",
            "is_archived": "BOOLEAN NOT NULL DEFAULT 0",
            "archived_at": "DATETIME",
            "archived_by_user_id": "VARCHAR",
        }

        for column_name, column_type in mounting_node_columns.items():

            _add_column_if_missing(

                connection,

                "mounting_nodes",

                column_name,

                column_type
            )

        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS mounting_node_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER NOT NULL,
                node_code VARCHAR(128) NOT NULL,
                node_name VARCHAR(255) NOT NULL,
                version_number INTEGER NOT NULL,
                event_type VARCHAR(32) NOT NULL DEFAULT 'update',
                snapshot JSON NOT NULL,
                created_by_user_id VARCHAR,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(node_id, version_number),
                FOREIGN KEY(created_by_user_id) REFERENCES users (id)
            )
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_mounting_node_versions_node_id
            ON mounting_node_versions (node_id)
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_mounting_node_versions_version_number
            ON mounting_node_versions (version_number)
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_fitting_hole_templates_bundle_key
            ON fitting_hole_templates (bundle_key)
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE projects
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE projects
            SET updated_at = CURRENT_TIMESTAMP
            WHERE updated_at IS NULL
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE project_versions
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )

        service_catalog_columns = {
            "article": "VARCHAR",
            "full_description": "TEXT",
            "last_synced_at": "DATETIME",
            "price_sync_status": "VARCHAR",
            "price_source_label": "VARCHAR",
            "owner_user_id": "VARCHAR",
            "rules_source_url": "VARCHAR",
            "rules_parsed_at": "DATETIME",
            "rules_parse_status": "VARCHAR",
        }

        for column_name, column_type in service_catalog_columns.items():

            _add_column_if_missing(

                connection,

                "service_catalog_items",

                column_name,

                column_type
            )

        user_columns = {
            "username": "VARCHAR",
            "phone": "VARCHAR",
            "registration_status": "VARCHAR",
            "city": "VARCHAR",
            "telegram_id": "VARCHAR",
            "phone_verified_at": "DATETIME",
            "last_username_change_at": "DATETIME",
            "trial_started_at": "DATETIME",
            "trial_ends_at": "DATETIME",
            "viyar_email": "VARCHAR",
            "viyar_password_secret": "VARCHAR",
            "viyar_cookie": "VARCHAR",
            "viyar_cookie_updated_at": "DATETIME",
            "viyar_last_auth_at": "DATETIME",
            "viyar_last_auth_status": "VARCHAR",
            "viyar_last_auth_error": "VARCHAR",
        }

        for column_name, column_type in user_columns.items():

            _add_column_if_missing(

                connection,

                "users",

                column_name,

                column_type
            )

        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS registration_identities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity_type VARCHAR NOT NULL,
                identity_value_normalized VARCHAR NOT NULL,
                first_user_id VARCHAR,
                verified_at DATETIME,
                trial_used_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(identity_type, identity_value_normalized)
            )
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_registration_identities_identity_type
            ON registration_identities (identity_type)
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_registration_identities_identity_value_normalized
            ON registration_identities (identity_value_normalized)
            """
        )

        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS registration_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR,
                channel VARCHAR NOT NULL,
                token_hash VARCHAR(64) NOT NULL,
                status_token_hash VARCHAR(64),
                expected_identity_type VARCHAR NOT NULL,
                expected_identity_value_normalized VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                attempts_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,
                expires_at DATETIME NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                verified_at DATETIME,
                consumed_at DATETIME,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(token_hash),
                UNIQUE(status_token_hash)
            )
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_registration_challenges_user_id
            ON registration_challenges (user_id)
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_registration_challenges_status
            ON registration_challenges (status)
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_registration_challenges_expires_at
            ON registration_challenges (expires_at)
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE users
            SET username = lower(substr(email, 1, instr(email, '@') - 1))
            WHERE (username IS NULL OR trim(username) = '')
              AND instr(email, '@') > 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM users AS existing_users
                  WHERE existing_users.id != users.id
                    AND lower(existing_users.username) = lower(substr(users.email, 1, instr(users.email, '@') - 1))
              )
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE users
            SET role = 'free'
            WHERE role IS NULL
               OR trim(role) = ''
               OR lower(role) IN ('user', 'guest', 'manager', 'viewer')
            """
        )

        material_import_job_columns = {
            "article": "VARCHAR",
            "category": "VARCHAR",
            "city": "VARCHAR",
            "owner_user_id": "VARCHAR",
            "status": "VARCHAR",
            "attempt_count": "INTEGER",
            "max_attempts": "INTEGER",
            "next_retry_at": "DATETIME",
            "last_error": "VARCHAR",
            "last_strategy": "VARCHAR",
            "last_source_url": "VARCHAR",
            "preferred_url": "VARCHAR",
            "debug_trace": "TEXT",
            "created_at": "DATETIME",
            "updated_at": "DATETIME",
            "completed_at": "DATETIME",
        }

        for column_name, column_type in material_import_job_columns.items():

            _add_column_if_missing(

                connection,

                "material_import_jobs",

                column_name,

                column_type
            )

        material_columns = {
            "source": "VARCHAR",
            "product_type": "VARCHAR",
            "description": "VARCHAR",
            "color": "VARCHAR",
            "dimensions": "VARCHAR",
            "thickness": "VARCHAR",
            "source_url": "VARCHAR",
            "owner_user_id": "VARCHAR",
            "is_default": "BOOLEAN NOT NULL DEFAULT 0",
            "image_cached_bytes": "BLOB",
            "image_cached_content_type": "VARCHAR",
            "image_source_url": "VARCHAR",
            "image_cached_hash": "VARCHAR",
            "imported_at": "DATETIME",
            "static_updated_at": "DATETIME",
        }

        for column_name, column_type in material_columns.items():

            _add_column_if_missing(

                connection,

                "materials",

                column_name,

                column_type
            )

        material_price_columns = {
            "old_price": "REAL",
            "is_promo": "BOOLEAN NOT NULL DEFAULT 0",
            "discount_percent": "REAL",
            "promo_label": "TEXT",
            "promo_valid_until": "DATE",
            "source_checked_at": "DATETIME",
            "currency": "VARCHAR",
            "availability": "VARCHAR",
            "updated_at": "DATETIME",
        }

        for column_name, column_type in material_price_columns.items():

            _add_column_if_missing(

                connection,

                "material_prices",

                column_name,

                column_type
            )

        connection.exec_driver_sql(
            """
            UPDATE material_prices
            SET updated_at = CURRENT_TIMESTAMP
            WHERE updated_at IS NULL
            """
        )

        connection.execute(
            text(
                """
                UPDATE materials
                SET is_default = 1
                WHERE article IN ('215557', '43102', '45791', '77792')
                """
            )
        )

        connection.execute(
            text(
                """
                DELETE FROM material_prices
                WHERE
                    (article = '215557' AND city = 'kyiv' AND CAST(price AS TEXT) IN ('850', '850.0'))
                    OR (article = '215557' AND city = 'lviv' AND CAST(price AS TEXT) IN ('870', '870.0'))
                    OR (article = '43102' AND city = 'kyiv' AND CAST(price AS TEXT) IN ('620', '620.0'))
                    OR (article = '43102' AND city = 'lviv' AND CAST(price AS TEXT) IN ('640', '640.0'))
                """
            )
        )

        material_edge_columns = {
            "image_cached_bytes": "BLOB",
            "image_cached_content_type": "VARCHAR",
            "image_source_url": "VARCHAR",
            "image_cached_hash": "VARCHAR",
            "source": "VARCHAR",
            "product_type": "VARCHAR",
            "imported_at": "DATETIME",
            "static_updated_at": "DATETIME",
        }

        for column_name, column_type in material_edge_columns.items():
            _add_column_if_missing(
                connection,
                "material_edge_options",
                column_name,
                column_type,
            )

        _add_column_if_missing(
            connection,
            "material_edge_prices",
            "currency",
            "VARCHAR",
        )

        _add_column_if_missing(
            connection,
            "material_edge_prices",
            "availability",
            "VARCHAR",
        )

        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS material_user_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_article VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                source VARCHAR,
                product_type VARCHAR,
                source_url VARCHAR,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(material_article, user_id)
            )
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_material_user_links_material_article
            ON material_user_links (material_article)
            """
        )

        connection.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_material_user_links_user_id
            ON material_user_links (user_id)
            """
        )

        fitting_columns = {
            "fitting_type": "VARCHAR",
            "fitting_group": "VARCHAR",
            "image_url": "VARCHAR",
            "image_cached_bytes": "BLOB",
            "image_cached_content_type": "VARCHAR",
            "source_url": "VARCHAR",
            "owner_user_id": "VARCHAR",
            "is_system": "BOOLEAN NOT NULL DEFAULT 1",
            "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            "sort_order": "INTEGER NOT NULL DEFAULT 0",
        }

        for column_name, column_type in fitting_columns.items():

            _add_column_if_missing(

                connection,

                "fittings",

                column_name,

                column_type
            )

        connection.exec_driver_sql(
            """
            UPDATE fittings
            SET is_system = 1
            WHERE is_system IS NULL
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE fittings
            SET is_active = 1
            WHERE is_active IS NULL
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE fittings
            SET sort_order = 0
            WHERE sort_order IS NULL
            """
        )


def seed_demo_access_users():

    seed_enabled = os.getenv(
        "SEED_DEMO_USERS",
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if not seed_enabled:

        return

    demo_password = "Demo12345!"

    demo_users = [
        ("admin@example.com", "admin"),
        ("free@example.com", "free"),
        ("pro@example.com", "pro"),
        ("premium@example.com", "premium"),
        ("manager@example.com", "free"),
    ]

    for email, role in demo_users:

        if get_user_by_email(email):

            continue

        create_managed_user(
            email=email,
            password=demo_password,
            role=role
        )


def init_database():

    Base.metadata.create_all(
        bind=engine
    )

    ensure_unified_legacy_schema()
    migrate_legacy_sqlite_to_unified_db(copy_fittings=False)

    upgrade_sqlite_schema()
    with engine.begin() as connection:
        ensure_fittings_foundation_schema(connection)
        ensure_fitting_products_schema(connection)
        ensure_fitting_taxonomy_schema(connection)
        ensure_mounting_schemes_schema(connection)
    _backfill_mounting_node_versions()
    seed_demo_access_users()

    seed_default_catalog_items()
    seed_default_viyar_service_catalog()


if __name__ == "__main__":

    init_database()

    print(
        "Database initialized"
    )
