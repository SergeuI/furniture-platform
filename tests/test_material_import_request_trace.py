from __future__ import annotations

import asyncio
import importlib
import json
import re
import sys
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from urllib.error import URLError

from fastapi.testclient import TestClient
from PIL import Image

from api.dependencies import auth as auth_dependencies
from api.routes import catalog as catalog_routes
from services.fitting_image_gallery_service import PreparedFittingGalleryImage


class MaterialImportRequestTraceTests(unittest.TestCase):
    @staticmethod
    def _build_jpeg_bytes(color: tuple[int, int, int] = (220, 180, 140)) -> bytes:
        buffer = BytesIO()
        image = Image.new("RGB", (120, 120), color=color)
        image.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()

    @staticmethod
    def _load_main_api():
        sys.modules.pop("main_api", None)

        with (
            patch("database.init_db.init_database"),
            patch("services.material_import_queue_service.start_material_import_queue_loop"),
            patch("services.material_import_queue_service.stop_material_import_queue_loop"),
        ):
            return importlib.import_module("main_api")

    @staticmethod
    def _admin_user():
        return type(
            "AdminUserStub",
            (),
            {
                "id": "admin-user",
                "email": "admin@example.com",
                "role": "admin",
                "city": "kyiv",
            },
        )()

    def test_safe_failure_emits_request_completion_without_material_stage_logs(self) -> None:
        main_api = self._load_main_api()

        fetch_mock = AsyncMock(
            return_value=(
                None,
                {
                    "strategy": "direct_url_html",
                    "source_url": "https://viyar.ua/ua/catalog/example/",
                    "trace": [],
                },
            )
        )

        with (
            patch.object(auth_dependencies, "get_user_from_token", return_value=self._admin_user()),
            patch.object(catalog_routes, "fetch_material_by_source_url_live_traced", new=fetch_mock),
            patch.object(catalog_routes, "_resolve_viyar_cookie_for_user", return_value=None),
            TestClient(main_api.app) as client,
            self.assertLogs("api", level="INFO") as captured,
        ):
            response = client.post(
                "/catalog/materials",
                json={
                    "article": "K533",
                    "category": "dsp",
                    "city": "kyiv",
                    "source_url": "https://viyar.ua/ua/catalog/example/",
                },
                headers={"Authorization": "Bearer admin-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertIn("VIYAR", response.json()["error"])
        self.assertIn("X-Request-ID", response.headers)

        log_output = "\n".join(captured.output)
        self.assertNotIn("material_import_trace", log_output)
        self.assertNotIn("REQUEST_START", log_output)
        self.assertNotIn("DIRECT_SOURCE_PARSE_START", log_output)
        self.assertNotIn("DIRECT_SOURCE_PARSE_END", log_output)
        self.assertNotIn("SAFE_FAILURE_RETURN", log_output)
        self.assertIn("REQUEST_COMPLETE", log_output)

        request_ids = set(re.findall(r"request_id=([a-zA-Z0-9-]+)", log_output))
        self.assertEqual(len(request_ids), 1)
        request_id = next(iter(request_ids))
        self.assertEqual(response.headers["X-Request-ID"], request_id)

    def test_parser_exception_emits_request_completion_without_material_stage_logs(self) -> None:
        main_api = self._load_main_api()

        fetch_mock = AsyncMock(side_effect=URLError("net::ERR_NETWORK_ACCESS_DENIED"))

        with (
            patch.object(auth_dependencies, "get_user_from_token", return_value=self._admin_user()),
            patch.object(catalog_routes, "fetch_material_by_source_url_live_traced", new=fetch_mock),
            patch.object(catalog_routes, "_resolve_viyar_cookie_for_user", return_value=None),
            TestClient(main_api.app) as client,
            self.assertLogs("api", level="INFO") as captured,
        ):
            response = client.post(
                "/catalog/materials",
                json={
                    "article": "K533",
                    "category": "dsp",
                    "city": "kyiv",
                    "source_url": "https://viyar.ua/ua/catalog/example/",
                },
                headers={"Authorization": "Bearer admin-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertIn("X-Request-ID", response.headers)

        log_output = "\n".join(captured.output)
        self.assertNotIn("material_import_trace", log_output)
        self.assertNotIn("DIRECT_SOURCE_PARSE_START", log_output)
        self.assertNotIn("DIRECT_SOURCE_PARSE_END", log_output)
        self.assertNotIn("ROUTE_EXCEPTION", log_output)
        self.assertIn("REQUEST_COMPLETE", log_output)
        self.assertIn("status=200", log_output)

    def test_material_import_uses_single_source_parse_without_remote_image_validation(self) -> None:
        main_api = self._load_main_api()

        parsed_material = {
            "article": "242944",
            "name": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800х2070х18 мм",
            "description": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3",
            "color": "Каштан",
            "dimensions": "2800x2070x18 мм",
            "thickness": "18 мм",
            "image": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
            "image_urls": [
                "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
                "https://www.viyar.ua/store/Items/photos/ph242944_MWJFJ.jpg",
            ],
            "price": 5800.98,
            "price_raw": "5800.98",
            "unit": "₴/лист",
            "brand": "Kronospan",
            "currency": "UAH",
            "availability": "В наявності",
            "characteristics": {
                "Тип основи": "ДСП",
                "Колекція": "Standart",
                "Площа": "5.796",
                "Текстура": "SN",
            },
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "source_site": "viyar",
            "external_product_id": None,
            "stock": None,
            "region": None,
        }
        persisted_item = {
            "id": "2126",
            "article": "242944",
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "source": "viyar",
            "category": "dsp",
            "product_type": "dsp",
            "owner_user_id": None,
            "is_default": True,
            "images": [],
            "supplier_offers": [],
        }
        fetch_mock = AsyncMock(return_value=(parsed_material, {"strategy": "direct_url_html"}))
        prices_mock = AsyncMock(side_effect=AssertionError("normal material import must not repeat source fetch per city"))
        upsert_calls: list[dict] = []
        image_fetch_mock = Mock(side_effect=AssertionError("VIYAR import must not validate remote images"))

        def _fake_upsert_material(**kwargs):
            upsert_calls.append(kwargs)
            gallery_images = list(kwargs.get("prepared_gallery_images") or [])
            return {
                **persisted_item,
                "images": [
                    {
                        "id": index + 1,
                        "source_url": image.source_url,
                        "sort_order": image.sort_order,
                        "is_primary": image.is_primary,
                        "content_type": image.content_type,
                    }
                    for index, image in enumerate(gallery_images)
                ],
            }

        with (
            patch.object(auth_dependencies, "get_user_from_token", return_value=self._admin_user()),
            patch.object(catalog_routes, "fetch_material_by_source_url_live_traced", new=fetch_mock),
            patch.object(catalog_routes, "_collect_material_prices_for_all_cities", new=prices_mock),
            patch.object(catalog_routes, "_resolve_viyar_cookie_for_user", return_value=None),
            patch.object(catalog_routes, "get_material_by_article", return_value=None),
            patch.object(catalog_routes, "_resolve_material_with_city_context", return_value=None),
            patch.object(catalog_routes, "validate_material_supplier_offer_identity", return_value={"status": "compatible"}),
            patch.object(catalog_routes, "get_supplier_by_code", return_value={"id": 1, "is_active": True}),
            patch.object(catalog_routes, "fetch_remote_image_payload", image_fetch_mock),
            patch.object(catalog_routes, "upsert_material", side_effect=_fake_upsert_material),
            patch.object(catalog_routes, "upsert_material_price"),
            patch.object(catalog_routes, "ensure_material_user_link"),
            patch.object(catalog_routes, "upsert_material_supplier_offer_for_import") as offer_mock,
            patch.object(catalog_routes, "create_audit_log"),
            patch.object(catalog_routes, "persist_viyar_recommended_edges_for_material_import") as edge_mock,
            TestClient(main_api.app) as client,
        ):
            response = client.post(
                "/catalog/materials",
                json={
                    "article": "242944",
                    "category": "dsp",
                    "city": "kyiv",
                    "source_url": "https://viyar.ua/ua/catalog/k533/",
                },
                headers={"Authorization": "Bearer admin-token"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["item"]["id"], "2126")
        self.assertEqual(len(body["item"]["images"]), 0)
        self.assertIsNone(body["recommended_edges"])
        fetch_mock.assert_awaited_once()
        prices_mock.assert_not_awaited()
        self.assertEqual(len(upsert_calls), 1)
        self.assertIsNone(upsert_calls[0]["prepared_gallery_images"])
        image_fetch_mock.assert_not_called()
        self.assertEqual(upsert_calls[0]["article"], "242944")
        self.assertEqual(upsert_calls[0]["source_url"], "https://viyar.ua/ua/catalog/k533/")
        self.assertEqual(upsert_calls[0]["image_source_url"], "https://viyar.ua/store/Items/photos/ph242944_lOLfy.jpg")
        self.assertEqual(upsert_calls[0]["dimensions"], "2800x2070x18 мм")
        self.assertEqual(offer_mock.call_args.kwargs["stock"], "В наявності")
        offer_call = offer_mock.call_args.kwargs
        self.assertEqual(
            json.loads(offer_call["source_payload_json"])["parsed_material"]["characteristics"],
            parsed_material["characteristics"],
        )
        self.assertEqual(
            json.loads(offer_call["source_payload_json"])["parsed_material"]["image_urls"],
            [
                "https://viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
                "https://viyar.ua/store/Items/photos/ph242944_MWJFJ.jpg",
            ],
        )
        edge_mock.assert_not_called()

    def test_material_import_keeps_gallery_when_city_context_is_refreshed(self) -> None:
        main_api = self._load_main_api()

        parsed_material = {
            "article": "242944",
            "name": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800х2070х18 мм",
            "description": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3",
            "color": "Каштан",
            "dimensions": "2800x2070x18 мм",
            "thickness": "18 мм",
            "image": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
            "image_urls": [
                "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
                "https://www.viyar.ua/store/Items/photos/ph242944_MWJFJ.jpg",
            ],
            "price": 5800.98,
            "price_raw": "5800.98",
            "unit": "₴/лист",
            "brand": "Kronospan",
            "currency": "UAH",
            "availability": "В наявності",
            "characteristics": {},
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "source_site": "viyar",
            "external_product_id": None,
            "stock": None,
            "region": None,
        }
        persisted_detail = {
            "id": "2126",
            "article": "242944",
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "source": "viyar",
            "category": "dsp",
            "product_type": "dsp",
            "owner_user_id": None,
            "is_default": True,
            "images": [
                {"id": 1, "content_type": "image/jpeg", "is_primary": True, "sort_order": 0, "source_url": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg"},
                {"id": 2, "content_type": "image/jpeg", "is_primary": False, "sort_order": 1, "source_url": "https://www.viyar.ua/store/Items/photos/ph242944_MWJFJ.jpg"},
            ],
            "prices": [
                {"city": "kyiv", "price": 5800.98, "currency": "UAH"},
            ],
            "supplier_offers": [],
        }
        city_context_item = {
            "id": "2126",
            "article": "242944",
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "source": "viyar",
            "category": "dsp",
            "product_type": "dsp",
            "owner_user_id": None,
            "is_default": True,
            "current_price": 5800.98,
            "current_price_city": "kyiv",
            "images": [],
        }
        gallery_payloads = {
            "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg": {
                "bytes": self._build_jpeg_bytes(),
                "content_type": "image/jpeg",
                "resolved_url": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
            },
            "https://www.viyar.ua/store/Items/photos/ph242944_MWJFJ.jpg": {
                "bytes": self._build_jpeg_bytes((120, 160, 200)),
                "content_type": "image/jpeg",
                "resolved_url": "https://www.viyar.ua/store/Items/photos/ph242944_MWJFJ.jpg",
            },
        }

        def _fake_fetch_remote_image_payload(image_url, city=None, cookie_override=None):
            return gallery_payloads.get(image_url)

        def _fake_upsert_material(**kwargs):
            gallery_images = list(kwargs.get("prepared_gallery_images") or [])
            return {
                **persisted_detail,
                "images": [
                    {
                        "id": index + 1,
                        "source_url": image.source_url,
                        "sort_order": image.sort_order,
                        "is_primary": image.is_primary,
                        "content_type": image.content_type,
                    }
                    for index, image in enumerate(gallery_images)
                ],
            }

        with (
            patch.object(auth_dependencies, "get_user_from_token", return_value=self._admin_user()),
            patch.object(catalog_routes, "fetch_material_by_source_url_live_traced", new=AsyncMock(return_value=(parsed_material, {"strategy": "direct_url_html"}))),
            patch.object(catalog_routes, "_resolve_viyar_cookie_for_user", return_value=None),
            patch.object(catalog_routes, "_collect_material_prices_for_all_cities", side_effect=AssertionError("normal material import must not repeat source fetch per city")),
            patch.object(catalog_routes, "get_material_by_article", return_value=persisted_detail),
            patch.object(catalog_routes, "list_materials", return_value=[city_context_item]),
            patch.object(catalog_routes, "validate_material_supplier_offer_identity", return_value={"status": "compatible"}),
            patch.object(catalog_routes, "get_supplier_by_code", return_value={"id": 1, "is_active": True}),
            patch.object(catalog_routes, "fetch_remote_image_payload", side_effect=_fake_fetch_remote_image_payload),
            patch.object(catalog_routes, "upsert_material", side_effect=_fake_upsert_material),
            patch.object(catalog_routes, "upsert_material_price"),
            patch.object(catalog_routes, "ensure_material_user_link"),
            patch.object(catalog_routes, "upsert_material_supplier_offer_for_import"),
            patch.object(catalog_routes, "create_audit_log"),
            patch.object(catalog_routes, "persist_viyar_recommended_edges_for_material_import") as edge_mock,
            TestClient(main_api.app) as client,
        ):
            response = client.post(
                "/catalog/materials",
                json={
                    "article": "242944",
                    "category": "dsp",
                    "city": "kyiv",
                    "source_url": "https://viyar.ua/ua/catalog/k533/",
                },
                headers={"Authorization": "Bearer admin-token"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["item"]["images"]), 2)
        self.assertEqual(body["item"]["current_price"], 5800.98)
        self.assertEqual(body["item"]["current_price_city"], "kyiv")
        self.assertEqual([image["sort_order"] for image in body["item"]["images"]], [0, 1])
        self.assertTrue(body["item"]["images"][0]["is_primary"])
        self.assertFalse(body["item"]["images"][1]["is_primary"])
        self.assertEqual(body["item"]["images"][0]["content_type"], "image/jpeg")
        edge_mock.assert_not_called()

    def test_gallery_helper_persists_prepared_images_without_creating_material(self) -> None:
        material = {
            "id": "2126",
            "article": "242944",
            "name": "K533",
            "description": "K533",
            "color": "K533",
            "dimensions": "2800x2070x18 мм",
            "thickness": "18 мм",
            "category": "dsp",
            "product_type": "dsp",
            "image": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
            "image_source_url": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "source": "viyar",
            "owner_user_id": None,
            "is_default": True,
            "imported_at": None,
        }
        prepared_gallery_image = PreparedFittingGalleryImage(
            sort_order=0,
            is_primary=True,
            source_url="https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
            image_bytes=b"fake-gallery-image",
            content_type="image/jpeg",
            sha256="abc123",
        )
        parsed_material = {
            "name": "K533",
            "description": "K533",
            "color": "K533",
            "dimensions": "2800x2070x18 мм",
            "thickness": "18 мм",
            "image": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
            "image_urls": [prepared_gallery_image.source_url],
            "source_url": material["source_url"],
            "product_type": "dsp",
        }

        async def run() -> tuple[dict, object, object]:
            with (
                patch.object(catalog_routes, "_resolve_viyar_cookie_for_user", return_value=None),
                patch.object(catalog_routes, "fetch_material_by_source_url_live_traced", new=AsyncMock(return_value=(parsed_material, {}))),
                patch.object(catalog_routes, "prefetch_material_image_cache", return_value={"bytes": b"fake-primary", "content_type": "image/jpeg", "resolved_url": prepared_gallery_image.source_url}),
                patch.object(catalog_routes, "_prepare_remote_material_gallery_images", return_value=(prepared_gallery_image,)),
                patch.object(catalog_routes, "upsert_material", return_value={**material, "images": [material]}),
                patch.object(catalog_routes, "update_material_image_cache"),
                patch.object(catalog_routes, "ensure_material_user_link"),
            ):
                return await catalog_routes._refresh_material_gallery_for_item(
                    material=material,
                    current_user=self._admin_user(),
                )

        refreshed_item, summary, warning = asyncio.run(run())

        self.assertEqual(summary.discovered, 1)
        self.assertEqual(summary.persisted, 1)
        self.assertEqual(summary.failed, 0)
        self.assertIsNone(warning)
        self.assertEqual(refreshed_item["id"], "2126")

    def test_edge_helper_persists_summary_without_touching_material(self) -> None:
        material = {
            "id": "2126",
            "article": "242944",
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "category": "dsp",
            "product_type": "dsp",
        }

        async def run() -> tuple[object, object, object]:
            with (
                patch.object(catalog_routes, "_resolve_viyar_cookie_for_user", return_value=None),
                patch.object(
                    catalog_routes,
                    "persist_viyar_recommended_edges_for_material_import",
                    new=AsyncMock(
                        return_value={
                            "summary": {"discovered": 4, "persisted": 3, "needs_review": 1, "failed": 0},
                            "review_items": [
                                {
                                    "article": "185187",
                                    "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                                    "reason": "missing_identity_fields",
                                    "missing_fields": ["width_mm"],
                                }
                            ],
                            "error": None,
                        }
                    ),
                ),
            ):
                return await catalog_routes._refresh_material_recommended_edges_for_item(
                    material=material,
                    material_id=2126,
                    current_user=self._admin_user(),
                )

        summary, warning, review_items = asyncio.run(run())

        self.assertEqual(summary.discovered, 4)
        self.assertEqual(summary.persisted, 3)
        self.assertEqual(summary.needs_review, 1)
        self.assertEqual(summary.failed, 0)
        self.assertIsNone(warning)
        self.assertEqual(review_items, [
            {
                "article": "185187",
                "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                "reason": "missing_identity_fields",
                "missing_fields": ["width_mm"],
            }
        ])

    def test_refresh_route_includes_review_items_when_edges_need_review(self) -> None:
        main_api = self._load_main_api()

        material_row = type("MaterialRow", (), {"article": "242944"})()
        material = {
            "article": "242944",
            "source_url": "https://viyar.ua/ua/catalog/k533/",
            "category": "dsp",
        }
        refreshed_item = {**material, "images": []}
        db_mock = MagicMock()
        db_mock.query.return_value.filter.return_value.first.return_value = material_row

        async def run():
            with (
                patch.object(auth_dependencies, "get_user_from_token", return_value=self._admin_user()),
                patch.object(catalog_routes, "SessionLocal", return_value=db_mock),
                patch.object(catalog_routes, "get_material_by_article", return_value=material),
                patch.object(catalog_routes, "_can_manage_material_item", return_value=True),
                patch.object(catalog_routes, "detect_material_source_site", return_value="viyar"),
                patch.object(catalog_routes, "_resolve_viyar_cookie_for_user", return_value=None),
                patch.object(
                    catalog_routes,
                    "persist_viyar_recommended_edges_for_material_import",
                    return_value={
                        "summary": {"discovered": 1, "persisted": 0, "needs_review": 1, "failed": 0},
                        "review_items": [
                            {
                                "article": "185187",
                                "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                                "reason": "missing_identity_fields",
                                "missing_fields": ["width_mm"],
                            }
                        ],
                        "error": None,
                    },
                ),
                patch.object(catalog_routes, "_resolve_material_with_city_context", return_value=refreshed_item),
                patch.object(catalog_routes, "create_audit_log"),
            ):
                return await catalog_routes.refresh_material_recommended_edges_route(
                    material_id=2126,
                    current_user=self._admin_user(),
                )

        body = asyncio.run(run())

        self.assertTrue(body["success"])
        self.assertEqual(body["summary"].needs_review, 1)
        self.assertEqual(body["review_items"], [
            {
                "article": "185187",
                "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                "reason": "missing_identity_fields",
                "missing_fields": ["width_mm"],
            }
        ])
