from __future__ import annotations

from io import BytesIO
from unittest.mock import patch
import unittest

from PIL import Image

from api.routes import catalog
from services import material_catalog_service


class MaterialCatalogImageResolutionTests(unittest.TestCase):
    @staticmethod
    def _build_jpeg_bytes(color: tuple[int, int, int] = (220, 180, 140)) -> bytes:
        buffer = BytesIO()
        image = Image.new("RGB", (120, 120), color=color)
        image.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()

    def test_resolve_material_image_payload_prefers_exact_bare_host_variant_before_article_guesses(self) -> None:
        control_url = (
            "https://viyar.ua/ua/catalog/"
            "dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/"
            "?ms_q=533"
        )
        exact_parser_url = "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg"
        bare_host_exact_url = "https://viyar.ua/store/Items/photos/ph242944_lOLfy.jpg"
        unsuffixed_guess = "https://viyar.ua/store/Items/photos/ph242944.jpg"
        jpeg_bytes = self._build_jpeg_bytes()
        calls: list[str] = []

        def _fake_fetch_binary(candidate: str, city=None, cookie_override=None):
            calls.append(candidate)
            if candidate == exact_parser_url:
                raise TimeoutError("simulated timeout on www host")
            if candidate == bare_host_exact_url:
                return jpeg_bytes, "image/jpeg", candidate
            if candidate == unsuffixed_guess:
                self.fail("unsuffixed guess must not be tried before exact bare-host suffixed URL")
            raise AssertionError(f"Unexpected candidate: {candidate}")

        with patch.object(material_catalog_service, "_fetch_binary", side_effect=_fake_fetch_binary):
            payload = material_catalog_service.resolve_material_image_payload(
                article="242944",
                stored_image=exact_parser_url,
                source_url=control_url,
                city="kyiv",
                cookie_override=None,
            )

        self.assertEqual(
            calls[:2],
            [
                exact_parser_url,
                bare_host_exact_url,
            ],
        )
        self.assertEqual(payload["resolved_url"], bare_host_exact_url)
        self.assertEqual(payload["content_type"], "image/jpeg")
        self.assertGreater(len(payload["bytes"]), 0)

    def test_extract_material_from_product_html_collects_gallery_images_in_order(self) -> None:
        html = """
            <html>
              <body>
                <h1>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</h1>
                <span class="text-code text-weight-bolder">185187</span>
                <div class="vr-card-slider">
                  <img src="/store/Items/photos/ph141342_main.jpg" />
                  <img data-src="https://www.viyar.ua/store/Items/photos/ph141342_2.jpg?size=640" />
                  <picture>
                    <source srcset="https://www.viyar.ua/store/Items/photos/ph141342_3_small.jpg 1x, https://www.viyar.ua/store/Items/photos/ph141342_3_big.jpg 2x" />
                    <img src="https://www.viyar.ua/store/Items/photos/ph141342_3_big.jpg" />
                  </picture>
                </div>
                <meta property="og:image" content="https://www.viyar.ua/store/Items/photos/ph141342_main.jpg" />
                <span class="price-actual">19.26</span>
                <span class="text-unit">₴/м.п.</span>
              </body>
            </html>
        """
        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="141342",
            source_url="https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22kh0-4mm-300-m-p-rehau/",
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["article"], "185187")
        self.assertEqual(parsed["image"], "https://www.viyar.ua/store/Items/photos/ph141342_main.jpg")
        self.assertEqual(
            parsed["image_urls"],
            [
                "https://www.viyar.ua/store/Items/photos/ph141342_main.jpg",
                "https://www.viyar.ua/store/Items/photos/ph141342_2.jpg",
                "https://www.viyar.ua/store/Items/photos/ph141342_3_big.jpg",
            ],
        )

    def test_extract_material_from_current_viyar_product_fragment(self) -> None:
        html = """
            <div id="about">
              <h1>ДСП Kronospan 3025 SN Дуб Сонома світлий 2800x2070x18 мм</h1>
              <div class="vr-code"><span>36617</span></div>
              <div class="price">
                <div class="product-card__price"><span>3 676.80</span>₴ / лист</div>
              </div>
              <div class="swiper-slide">
                <img src="https://viyar.ua/cdn-cgi/image/w=1156,h=1156,f=webp/https://viyar.ua/upload/photos/ph36617.jpg" />
              </div>
              <div class="swiper-slide">
                <img src="https://viyar.ua/upload/photos/ph36617_2.jpg" />
              </div>
            </div>
        """

        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="https://viyar.ua/ua/catalog/current-product/",
            source_url="https://viyar.ua/ua/catalog/current-product/",
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["name"], "ДСП Kronospan 3025 SN Дуб Сонома світлий 2800x2070x18 мм")
        self.assertEqual(parsed["article"], "36617")
        self.assertEqual(parsed["price"], 3676.80)
        self.assertEqual(parsed["unit"], "лист")
        self.assertEqual(parsed["thickness"], "18 мм")
        self.assertEqual(parsed["dimensions"], "2800x2070x18 мм")
        self.assertEqual(len(parsed["image_urls"]), 2)
        self.assertNotEqual(parsed["article"], parsed["source_url"])

    def test_extract_material_from_viyar_code_label_product_fragment(self) -> None:
        html = """
            <div id="about">
              <div class="card-info-head">
                <h1>ДСП Kronospan K 351 RT Іржавий камінь 2800x2070x18 мм</h1>
                <div class="card-info-head__code"><span>Код:</span><b>69962</b></div>
              </div>
            </div>
        """

        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="https://viyar.ua/ua/catalog/k351-rt/",
            source_url="https://viyar.ua/ua/catalog/k351-rt/",
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["article"], "69962")

    def test_extract_material_from_viyar_characteristics_fragment(self) -> None:
        html = """
            <section id="characteristics">
              <div class="characteristics-group">
                <table>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Тип основи:</td>
                    <td class="vr-block-char__value">ДСП</td>
                  </tr>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Товщина, мм:</td>
                    <td class="vr-block-char__value">18</td>
                  </tr>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Ширина, мм:</td>
                    <td class="vr-block-char__value">2070</td>
                  </tr>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Довжина, мм:</td>
                    <td class="vr-block-char__value">2800</td>
                  </tr>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Колекція:</td>
                    <td class="vr-block-char__value">Standart</td>
                  </tr>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Площа м кв:</td>
                    <td class="vr-block-char__value">5.796</td>
                  </tr>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Текстура поверхні (лицьова):</td>
                    <td class="vr-block-char__value">SN</td>
                  </tr>
                  <tr class="vr-block-char__tr">
                    <td class="vr-block-char__name">Текстура extra:</td>
                    <td class="vr-block-char__value">Збережено</td>
                  </tr>
                </table>
              </div>
            </section>
        """

        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="69962",
            source_url="https://viyar.ua/ua/catalog/k351-rt/",
        )

        self.assertIsNotNone(parsed)
        characteristics = parsed["characteristics"]
        self.assertGreater(len(characteristics), 0)
        self.assertEqual(characteristics["Тип основи"], "ДСП")
        self.assertEqual(characteristics["Товщина, мм"], "18")
        self.assertEqual(characteristics["Ширина, мм"], "2070")
        self.assertEqual(characteristics["Колекція"], "Standart")
        self.assertEqual(characteristics["Площа м кв"], "5.796")
        self.assertEqual(characteristics["Текстура поверхні (лицьова)"], "SN")
        self.assertEqual(parsed["thickness"], "18 мм")
        self.assertEqual(parsed["dimensions"], "2800x2070x18 мм")

    def test_extracts_viyar_availability_from_current_product_label(self) -> None:
        html = """
            <div id="about">
              <h1>ДСП Kronospan K520 2800x2070x18 мм</h1>
              <div class="vr-code"><span>189874</span></div>
              <div class="product-card__price"><span>100</span> ₴</div>
              <span class="productLabel">В наявності</span>
            </div>
        """

        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="189874",
            source_url="https://viyar.ua/ua/catalog/example/",
        )

        self.assertEqual(parsed["availability"], "В наявності")

    def test_missing_viyar_availability_stays_null(self) -> None:
        html = """
            <div id="about">
              <h1>ДСП Kronospan K520 2800x2070x18 мм</h1>
              <div class="vr-code"><span>189874</span></div>
              <div class="product-card__price"><span>100</span> ₴</div>
            </div>
        """

        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="189874",
            source_url="https://viyar.ua/ua/catalog/example/",
        )

        self.assertIsNone(parsed["availability"])

    def test_extracts_branch_availability_after_viyar_heading(self) -> None:
        html = """
            <div id="about">
              <h1>ДСП Kronospan K520 2800x2070x18 мм</h1>
              <div class="availability-panel">
                <h3>Наявність на філіях</h3>
                <div>б-р, Вацлава Гавела, 16</div>
                <div>В наявності</div>
                <div>вул. Віскозна, 3</div>
                <div>В наявності</div>
              </div>
              <section>Доставка та оплата</section>
              <div class="recommended"><span class="productLabel">Немає в наявності</span></div>
            </div>
        """

        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="26537",
            source_url="https://viyar.ua/ua/catalog/example/",
        )

        self.assertEqual(parsed["availability"], "В наявності")

    def test_extracts_out_of_stock_branch_status(self) -> None:
        html = """
            <div id="about">
              <h1>ДСП Kronospan K520 2800x2070x18 мм</h1>
              <div>
                <h3>Наявність на філіях</h3>
                <div>б-р, Вацлава Гавела, 16</div>
                <div>Немає в наявності</div>
              </div>
              <section>Характеристики</section>
            </div>
        """

        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="26537",
            source_url="https://viyar.ua/ua/catalog/example/",
        )

        self.assertEqual(parsed["availability"], "Немає в наявності")

    def test_extract_material_from_product_html_filters_technical_gallery_entries(self) -> None:
        html = """
            <html>
              <body>
                <h1>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</h1>
                <span class="text-code text-weight-bolder">185187</span>
                <div class="vr-card-slider">
                  <img src="https://www.viyar.ua/store/Items/photos/ph141342_main.jpg" />
                  <img data-src="https://www.viyar.ua/store/Items/photos/ph141342_main.jpg?size=640" />
                  <img src="https://www.viyar.ua/assets/icons/placeholder.svg" />
                  <img src="https://www.youtube.com/embed/abc123" />
                  <img src="https://www.viyar.ua/store/Items/photos/ph141342_2.jpg" />
                  <picture>
                    <source srcset="https://www.viyar.ua/store/Items/photos/ph141342_3_small.jpg 1x, https://www.viyar.ua/store/Items/photos/ph141342_3_big.jpg 2x" />
                  </picture>
                </div>
                <meta property="og:image" content="https://www.viyar.ua/store/Items/photos/ph141342_main.jpg" />
                <span class="price-actual">19.26</span>
                <span class="text-unit">₴/м.п.</span>
              </body>
            </html>
        """
        parsed = material_catalog_service._extract_material_from_product_html(  # noqa: SLF001
            html,
            article="141342",
            source_url="https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22kh0-4mm-300-m-p-rehau/",
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(
            parsed["image_urls"],
            [
                "https://www.viyar.ua/store/Items/photos/ph141342_main.jpg",
                "https://www.viyar.ua/store/Items/photos/ph141342_2.jpg",
                "https://www.viyar.ua/store/Items/photos/ph141342_3_big.jpg",
            ],
        )

    def test_resolve_material_gallery_image_payload_prefers_original_over_thumbnail(self) -> None:
        thumbnail_url = "https://www.viyar.ua/upload/resize_cache/photos/100_100_1/ph189874.jpg"
        preferred_original_url = "https://www.viyar.ua/store/Items/photos/ph189874.jpg"
        jpeg_bytes = self._build_jpeg_bytes()
        calls: list[str] = []

        def _fake_fetch_binary(candidate: str, city=None, cookie_override=None):
            calls.append(candidate)
            if candidate == preferred_original_url:
                return jpeg_bytes, "image/jpeg", candidate
            if candidate == thumbnail_url:
                self.fail("thumbnail must not win when original/high-res candidate exists")
            raise AssertionError(f"Unexpected candidate: {candidate}")

        with patch.object(material_catalog_service, "_fetch_binary", side_effect=_fake_fetch_binary):
            payload = material_catalog_service.resolve_material_gallery_image_payload(
                article="189874",
                stored_image=thumbnail_url,
                source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                city="kyiv",
                cookie_override=None,
            )

        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(calls[0], preferred_original_url)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["resolved_url"], preferred_original_url)
        self.assertEqual(payload["content_type"], "image/jpeg")

    def test_prepare_remote_material_gallery_images_uses_direct_image_fetches_and_keeps_valid_ones(self) -> None:
        gallery_payloads = {
            "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg": {
                "bytes": self._build_jpeg_bytes((220, 180, 140)),
                "content_type": "image/jpeg",
                "resolved_url": "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg",
            },
            "https://www.viyar.ua/store/Items/photos/ph189874_3.jpg": {
                "bytes": self._build_jpeg_bytes((140, 180, 220)),
                "content_type": "image/jpeg",
                "resolved_url": "https://www.viyar.ua/store/Items/photos/ph189874_3.jpg",
            },
        }

        def _fake_fetch_remote_image_payload(image_url, city=None, cookie_override=None):
            return gallery_payloads.get(image_url)

        with (
            patch.object(catalog, "fetch_remote_image_payload", side_effect=_fake_fetch_remote_image_payload),
            patch.object(catalog, "resolve_material_gallery_image_payload") as resolve_mock,
        ):
            prepared = catalog._prepare_remote_material_gallery_images(  # noqa: SLF001
                [
                    "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg",
                    "https://www.viyar.ua/store/Items/photos/ph189874_2.jpg",
                    "https://www.viyar.ua/store/Items/photos/ph189874_3.jpg",
                ],
                article="189874",
                source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                selected_city="kyiv",
                cookie_override=None,
            )

        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared or ()), 2)
        self.assertEqual([image.source_url for image in prepared or ()], [
            "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg",
            "https://www.viyar.ua/store/Items/photos/ph189874_3.jpg",
        ])
        resolve_mock.assert_not_called()

    def test_prepare_remote_material_gallery_images_skips_invalid_items_and_keeps_valid_ones(self) -> None:
        gallery_payloads = {
            "https://www.viyar.ua/store/Items/photos/ph189874_2.jpg": {
                "bytes": self._build_jpeg_bytes((220, 180, 140)),
                "content_type": "image/jpeg",
                "resolved_url": "https://www.viyar.ua/store/Items/photos/ph189874_2.jpg",
            },
        }

        def _fake_fetch_remote_image_payload(image_url, city=None, cookie_override=None):
            return gallery_payloads.get(image_url)

        with (
            patch.object(catalog, "fetch_remote_image_payload", side_effect=_fake_fetch_remote_image_payload),
            patch.object(catalog, "resolve_material_gallery_image_payload") as resolve_mock,
        ):
            prepared = catalog._prepare_remote_material_gallery_images(  # noqa: SLF001
                [
                    "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg",
                    "https://www.viyar.ua/store/Items/photos/ph189874_2.jpg",
                ],
                article="189874",
                source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                selected_city="kyiv",
                cookie_override=None,
            )

        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared or ()), 1)
        self.assertEqual(prepared[0].source_url, "https://www.viyar.ua/store/Items/photos/ph189874_2.jpg")
        self.assertTrue(prepared[0].is_primary)
        resolve_mock.assert_not_called()

    def test_prepare_remote_material_gallery_images_filters_duplicates_and_technical_candidates_before_fetch(self) -> None:
        gallery_payloads = {
            "https://viyar.ua/store/Items/photos/ph189874_1.jpg": {
                "bytes": self._build_jpeg_bytes((220, 180, 140)),
                "content_type": "image/jpeg",
                "resolved_url": "https://viyar.ua/store/Items/photos/ph189874_1.jpg",
            },
            "https://viyar.ua/store/Items/photos/ph189874_2.jpg": {
                "bytes": self._build_jpeg_bytes((140, 180, 220)),
                "content_type": "image/jpeg",
                "resolved_url": "https://viyar.ua/store/Items/photos/ph189874_2.jpg",
            },
            "https://viyar.ua/store/Items/photos/ph189874_3.jpg": {
                "bytes": self._build_jpeg_bytes((180, 140, 220)),
                "content_type": "image/jpeg",
                "resolved_url": "https://viyar.ua/store/Items/photos/ph189874_3.jpg",
            },
        }
        calls: list[str] = []

        def _fake_fetch_remote_image_payload(image_url, city=None, cookie_override=None):
            calls.append(image_url)
            return gallery_payloads.get(image_url)

        with (
            patch.object(catalog, "fetch_remote_image_payload", side_effect=_fake_fetch_remote_image_payload),
            patch.object(catalog, "resolve_material_gallery_image_payload") as resolve_mock,
        ):
            prepared = catalog._prepare_remote_material_gallery_images(  # noqa: SLF001
                [
                    "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg",
                    "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg?size=640",
                    "https://www.viyar.ua/assets/icons/placeholder.svg",
                    "https://www.youtube.com/embed/abc123",
                    "https://www.viyar.ua/store/Items/photos/ph189874_2.jpg",
                    "https://www.viyar.ua/store/Items/photos/ph189874_3.jpg",
                ],
                article="189874",
                source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                selected_city="kyiv",
                cookie_override=None,
            )

        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared or ()), 3)
        self.assertEqual(
            calls,
            [
                "https://viyar.ua/store/Items/photos/ph189874_1.jpg",
                "https://viyar.ua/store/Items/photos/ph189874_2.jpg",
                "https://viyar.ua/store/Items/photos/ph189874_3.jpg",
            ],
        )
        self.assertEqual(
            [image.source_url for image in prepared or ()],
            [
                "https://viyar.ua/store/Items/photos/ph189874_1.jpg",
                "https://viyar.ua/store/Items/photos/ph189874_2.jpg",
                "https://viyar.ua/store/Items/photos/ph189874_3.jpg",
            ],
        )
        self.assertTrue(prepared[0].is_primary)
        self.assertFalse(prepared[1].is_primary)
        self.assertFalse(prepared[2].is_primary)
        resolve_mock.assert_not_called()

    def test_prepare_remote_material_gallery_images_reuses_cached_primary_without_refetch(self) -> None:
        primary_bytes = self._build_jpeg_bytes((220, 180, 140))
        gallery_payloads = {
            "https://viyar.ua/store/Items/photos/ph189874_2.jpg": {
                "bytes": self._build_jpeg_bytes((140, 180, 220)),
                "content_type": "image/jpeg",
                "resolved_url": "https://viyar.ua/store/Items/photos/ph189874_2.jpg",
            },
        }
        calls: list[str] = []

        def _fake_fetch_remote_image_payload(image_url, city=None, cookie_override=None):
            calls.append(image_url)
            return gallery_payloads.get(image_url)

        with (
            patch.object(catalog, "fetch_remote_image_payload", side_effect=_fake_fetch_remote_image_payload),
            patch.object(catalog, "resolve_material_gallery_image_payload") as resolve_mock,
        ):
            prepared = catalog._prepare_remote_material_gallery_images(  # noqa: SLF001
                [
                    "https://www.viyar.ua/store/Items/photos/ph189874_1.jpg",
                    "https://www.viyar.ua/store/Items/photos/ph189874_2.jpg",
                ],
                article="189874",
                source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                selected_city="kyiv",
                cookie_override=None,
                existing_primary_bytes=primary_bytes,
                existing_primary_content_type="image/jpeg",
            )

        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared or ()), 2)
        self.assertEqual(calls, ["https://viyar.ua/store/Items/photos/ph189874_2.jpg"])
        self.assertEqual(
            [image.source_url for image in prepared or ()],
            [
                "https://viyar.ua/store/Items/photos/ph189874_1.jpg",
                "https://viyar.ua/store/Items/photos/ph189874_2.jpg",
            ],
        )
        self.assertTrue(prepared[0].is_primary)
        self.assertFalse(prepared[1].is_primary)
        resolve_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
