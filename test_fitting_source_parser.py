from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import preview_fitting_import
from services.fitting_source_parser import parse_fitting_source_metadata


KRONAS_HINGE_HTML = """
<html>
  <head>
    <title>Petlja nakladnaja bez pruzhiny</title>
    <meta property="og:title" content="Петля накладна без пружини GIFF PRIME D35 H0 нікель">
    <meta name="description" content="Накладна петля GIFF PRIME для меблів.">
    <meta itemprop="price" content="29.97">
    <meta itemprop="priceCurrency" content="UAH">
  </head>
  <body>
    <h1 itemprop="name">Петля накладна без пружини Clip-On GIFF PRIME D35 H0 нікель</h1>
    <div class="productLabel">Є в наявності</div>
    <div id="artikul" itemprop="sku">118442</div>
    <input name="artikulu" value="118442">
    <div class="productImageBlock__slider">
      <div class="js-productImage" data-src="/Media/images/catalog/original/118442_1.jpg"></div>
      <div class="js-productImage"><img data-src="/Media/images/catalog/original/118442_2.jpg"></div>
      <div class="js-productImage"><img src="/Media/images/catalog/original/118442_3.jpg"></div>
      <div class="js-productImage" data-large="/Media/images/catalog/big/118442_4.jpg">
        <img src="/Media/images/catalog/original/118442_3.jpg">
      </div>
    </div>
    <div class="productAttr">
      <div class="productAttr__key">Виробник:</div><div class="productAttr__value">GIFF PRIME</div>
      <div class="productAttr__key">Единица измерения:</div><div class="productAttr__value">шт.</div>
      <div class="productAttr__key">H:</div><div class="productAttr__value">0</div>
      <div class="productAttr__key">Тип:</div><div class="productAttr__value">Clip-On</div>
      <div class="productAttr__key">Ресурс:</div><div class="productAttr__value">100000</div>
      <div class="productAttr__key">Диаметр чашки:</div><div class="productAttr__value">35</div>
      <div class="productAttr__key">Кут відкривання:</div><div class="productAttr__value">105°</div>
      <div class="productAttr__key">Матеріал:</div><div class="productAttr__value">сталь</div>
      <div class="productAttr__key">Колір:</div><div class="productAttr__value">нікель</div>
    </div>
    <div class="productTabs__content is-active">
      <div class="view-text">
        <p>Короткий опис петлі для меблів.</p>
        <p>Довгий SEO-текст не потрібен.</p>
      </div>
    </div>
  </body>
</html>
"""


KRONAS_CONFIRMAT_HTML = """
<html>
  <head>
    <title>Konfirmat 6-ti grannik 70h50</title>
    <meta property="og:title" content="Конфірмат 6-ти гранник 70х50">
    <meta itemprop="description" content="Короткий опис конфірмата.">
    <meta itemprop="priceCurrency" content="грн">
  </head>
  <body>
    <h1 itemprop="name">Конфірмат 6-ти гранник 70х50</h1>
    <div class="productLabel">Під замовлення</div>
    <input name="artikulu" value="07733">
    <span itemprop="mpn">07733</span>
    <div id="price" data-price="0.85">0,85 грн</div>
    <div class="productImageBlock__slider">
      <div class="js-productImage" data-src="/Media/images/catalog/original/07733_1.jpg"></div>
      <div class="js-productImage"><img src="/Media/images/catalog/original/07733_2.jpg"></div>
      <div class="js-productImage"><img src="/Media/images/catalog/original/07733_2.jpg"></div>
    </div>
    <div class="productAttr">
      <div class="productAttr__key">Виробник:</div><div class="productAttr__value">GIFF</div>
      <div class="productAttr__key">Одиниця виміру:</div><div class="productAttr__value">шт.</div>
      <div class="productAttr__key">d1:</div><div class="productAttr__value">7</div>
      <div class="productAttr__key">d2:</div><div class="productAttr__value">10</div>
      <div class="productAttr__key">d3:</div><div class="productAttr__value">4</div>
      <div class="productAttr__key">S:</div><div class="productAttr__value">4</div>
      <div class="productAttr__key">I:</div><div class="productAttr__value">50</div>
      <div class="productAttr__key">Матеріал:</div><div class="productAttr__value">металл</div>
    </div>
  </body>
</html>
"""


VIYAR_HTML = """
<html>
  <head>
    <title>Viyar product</title>
    <meta property="og:title" content="Viyar product">
    <meta property="og:image" content="https://viyar.ua/store/Items/photos/ph12345.jpg">
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Viyar product",
        "sku": "12345",
        "brand": {"name": "ViyarBrand"},
        "image": [
          "https://viyar.ua/store/Items/photos/ph12345.jpg",
          "https://viyar.ua/store/Items/photos/ph12345-2.jpg"
        ],
        "offers": {
          "@type": "Offer",
          "price": 12.34,
          "priceCurrency": "UAH",
          "availability": "https://schema.org/InStock"
        }
      }
    </script>
  </head>
  <body>
    <h1 class="text text-weight-dark">Viyar product</h1>
    <span class="text-code text-weight-bolder">12345</span>
    <span id="product_price">12.34 ₴</span>
    <span class="text-unit">шт.</span>
    <table>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Виробник:</td>
        <td class="vr-block-char__value">ViyarBrand</td>
      </tr>
    </table>
  </body>
</html>
"""


class KronasParserTests(unittest.IsolatedAsyncioTestCase):
    async def _parse_with_html(self, url: str, html: str) -> dict:
        async def fake_fetch_html(requested_url: str):
            return 200, requested_url, html

        with patch("services.fitting_source_parser._fetch_html", new=fake_fetch_html):
            return await parse_fitting_source_metadata(url)

    async def test_kronas_hinge_contract(self) -> None:
        url = (
            "https://kronas.com.ua/furnitura-270/petli-i-komplektuyushhie-334/"
            "petli-dlya-dsp-454/petli-standartnye-335/"
            "petlja-nakladnaja-bez-pruzhiny-clip-on-giff-prime-d35-h0-nikel"
        )
        result = await self._parse_with_html(url, KRONAS_HINGE_HTML)

        self.assertTrue(result["success"])
        self.assertEqual(result["source_site"], "kronas")
        self.assertEqual(result["article"], "118442")
        self.assertEqual(result["brand"], "GIFF PRIME")
        self.assertEqual(result["price"], 29.97)
        self.assertEqual(result["currency"], "UAH")
        self.assertEqual(result["unit"], "шт.")
        self.assertEqual(result["availability"], "В наявності")
        self.assertEqual(result["image_url"], result["image_urls"][0])
        self.assertEqual(len(result["image_urls"]), 3)
        self.assertEqual(result["image_urls"][0], "https://kronas.com.ua/Media/images/catalog/original/118442_1.jpg")
        self.assertNotIn("big/118442_4.jpg", " ".join(result["image_urls"]))
        self.assertEqual(
            result["description"],
            "Накладна петля GIFF PRIME для меблів.",
        )

        self.assertEqual(result["characteristics"]["H"], "0")
        self.assertEqual(result["characteristics"]["Тип"], "Clip-On")
        self.assertEqual(result["characteristics"]["Ресурс"], "100000")
        self.assertEqual(result["characteristics"]["Диаметр чашки"], "35")
        self.assertEqual(result["characteristics"]["Кут відкривання"], "105°")
        self.assertEqual(result["characteristics"]["Матеріал"], "сталь")
        self.assertEqual(result["characteristics"]["Колір"], "нікель")

    async def test_kronas_confirmat_contract(self) -> None:
        url = (
            "https://kronas.com.ua/furnitura-270/krepyozhnaya-furnitura-365/"
            "styazhki-392/styazhka-konfirmat-s-potajnoj-golovkoj-shestigrannik-zaglushki-393/"
            "konfermat-6-ti-grannik-70h50-7453"
        )
        result = await self._parse_with_html(url, KRONAS_CONFIRMAT_HTML)

        self.assertTrue(result["success"])
        self.assertEqual(result["source_site"], "kronas")
        self.assertEqual(result["article"], "07733")
        self.assertEqual(result["brand"], "GIFF")
        self.assertEqual(result["price"], 0.85)
        self.assertEqual(result["currency"], "UAH")
        self.assertEqual(result["unit"], "шт.")
        self.assertEqual(result["availability"], "Під замовлення")
        self.assertEqual(len(result["image_urls"]), 2)
        self.assertEqual(result["image_url"], result["image_urls"][0])
        self.assertEqual(result["image_urls"][0], "https://kronas.com.ua/Media/images/catalog/original/07733_1.jpg")
        self.assertEqual(result["characteristics"]["d1"], "7")
        self.assertEqual(result["characteristics"]["d2"], "10")
        self.assertEqual(result["characteristics"]["d3"], "4")
        self.assertEqual(result["characteristics"]["S"], "4")
        self.assertEqual(result["characteristics"]["I"], "50")
        self.assertEqual(result["characteristics"]["Матеріал"], "металл")
        self.assertEqual(result["description"], "Короткий опис конфірмата.")

    async def test_viyar_regression_still_parses_basic_fields(self) -> None:
        url = "https://viyar.ua/test-product"

        async def fake_fetch_html(requested_url: str):
            return 200, requested_url, VIYAR_HTML

        with patch("services.fitting_source_parser._fetch_html", new=fake_fetch_html):
            result = await parse_fitting_source_metadata(url)

        self.assertTrue(result["success"])
        self.assertEqual(result["source_site"], "viyar")
        self.assertEqual(result["article"], "12345")
        self.assertEqual(result["brand"], "ViyarBrand")
        self.assertEqual(result["price"], 12.34)
        self.assertEqual(result["currency"], "UAH")
        self.assertEqual(result["unit"], "шт.")
        self.assertEqual(result["availability"], "В наявності")
        self.assertEqual(result["image_url"], "https://viyar.ua/store/Items/photos/ph12345.jpg")
        self.assertEqual(result["image_urls"][0], "https://viyar.ua/store/Items/photos/ph12345.jpg")
        self.assertEqual(result["characteristics"]["Виробник"], "ViyarBrand")


class PreviewImportTempDbTests(unittest.TestCase):
    def test_temp_db_apply_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "preview.db"
            self._create_preview_db(database_path)

            parsed = {
                "success": True,
                "source_site": "kronas",
                "final_url": "https://kronas.com.ua/test",
                "name": "Demo part",
                "description": "Demo part description",
                "article": "118442",
                "price": 29.97,
                "price_raw": "29.97",
                "unit": "шт.",
                "image_url": "https://kronas.com.ua/Media/images/catalog/original/118442_1.jpg",
                "image_urls": [
                    "https://kronas.com.ua/Media/images/catalog/original/118442_1.jpg",
                    "https://kronas.com.ua/Media/images/catalog/original/118442_2.jpg",
                ],
                "brand": "GIFF PRIME",
                "currency": "UAH",
                "availability": "В наявності",
                "characteristics": {"H": "0"},
            }
            image_info = {
                "bytes": b"image-bytes",
                "bytes_length": len(b"image-bytes"),
                "content_type": "image/jpeg",
                "sha256": "ignored",
                "real_format": "JPEG",
                "resolved_url": parsed["image_url"],
            }
            source_payload_json = preview_fitting_import._build_source_payload_json(
                source_url="https://kronas.com.ua/test",
                parsed=parsed,
                image_info=image_info,
                city="Київ",
                timestamp_iso=preview_fitting_import._utc_now_iso(),
            )
            source_payload_json_text = json.dumps(source_payload_json, ensure_ascii=False)

            with redirect_stdout(StringIO()):
                exit_code, inserted_id = preview_fitting_import._apply_insert(
                    database_path=database_path,
                    article="118442",
                    city="Київ",
                    source_url="https://kronas.com.ua/test",
                    parsed=parsed,
                    image_info=image_info,
                    source_payload_json_text=source_payload_json_text,
                )

            self.assertEqual(exit_code, 0)
            self.assertGreater(inserted_id, 0)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                row_count = connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0]
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(row_count, 1)
            self.assertEqual(str(integrity).lower(), "ok")
            self.assertEqual(foreign_keys, [])

            with redirect_stdout(StringIO()):
                duplicate_exit_code, duplicate_inserted_id = preview_fitting_import._apply_insert(
                    database_path=database_path,
                    article="118442",
                    city="Київ",
                    source_url="https://kronas.com.ua/test",
                    parsed=parsed,
                    image_info=image_info,
                    source_payload_json_text=source_payload_json_text,
                )

            self.assertEqual(duplicate_exit_code, 2)
            self.assertEqual(duplicate_inserted_id, 0)

            with sqlite3.connect(database_path) as connection:
                row_count_after_duplicate = connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0]
                integrity_after_duplicate = connection.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_keys_after_duplicate = connection.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(row_count_after_duplicate, 1)
            self.assertEqual(str(integrity_after_duplicate).lower(), "ok")
            self.assertEqual(foreign_keys_after_duplicate, [])

    @staticmethod
    def _create_preview_db(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    brand TEXT,
                    city TEXT NOT NULL,
                    price REAL,
                    currency TEXT,
                    unit TEXT,
                    source TEXT,
                    source_url TEXT,
                    image_url TEXT,
                    image_cached_bytes BLOB,
                    image_cached_content_type TEXT,
                    source_payload_json TEXT,
                    parsed_at TEXT,
                    price_updated_at TEXT
                )
                """
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
