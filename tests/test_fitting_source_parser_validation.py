from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from services import fitting_source_parser as parser


class FittingSourceParserValidationTests(IsolatedAsyncioTestCase):
    async def test_source_preview_rejects_error_page(self) -> None:
        error_html = """
            <html>
              <head><title>Error 404</title></head>
              <body>
                <h1>Error 404</h1>
                <p>Not Found</p>
              </body>
            </html>
        """

        with patch.object(
            parser,
            "_fetch_html",
            new=AsyncMock(return_value=(200, "https://viyar.ua/ua/catalog/missing", error_html)),
        ):
            result = await parser.parse_fitting_source_metadata("https://viyar.ua/ua/catalog/missing")

        self.assertFalse(result["success"])
        self.assertIn("не вдалося", result["error"].lower())

    async def test_source_preview_accepts_valid_viyar_product(self) -> None:
        valid_html = """
            <html>
              <head>
                <title>VIYAR Product</title>
                <meta property="og:image" content="https://cdn.example.com/image.jpg">
              </head>
              <body>
                <h1 class="text text-weight-dark">VIYAR Product</h1>
                <span class="text-code text-weight-bolder">123456</span>
                <span id="product_price">99.50</span>
              </body>
            </html>
        """

        with patch.object(
            parser,
            "_fetch_html",
            new=AsyncMock(return_value=(200, "https://viyar.ua/ua/catalog/product", valid_html)),
        ):
            result = await parser.parse_fitting_source_metadata("https://viyar.ua/ua/catalog/product")

        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "VIYAR Product")
        self.assertEqual(result["article"], "123456")
        self.assertEqual(result["image_url"], "https://cdn.example.com/image.jpg")

    async def test_source_preview_filters_kronas_non_image_gallery_entries(self) -> None:
        kronas_html = """
            <html>
              <head>
                <title>Петля накладная c доводчиком Clip-on 3D GIFF PRIME d=35 H=0 черный никель</title>
                <meta itemprop="price" content="71.77">
                <meta itemprop="priceCurrency" content="UAH">
              </head>
              <body>
                <h1>Петля накладная c доводчиком Clip-on 3D GIFF PRIME d=35 H=0 черный никель</h1>
                <span id="artikul" itemprop="sku">134376</span>
                <div class="productLabel">Є в наявності</div>
                <div class="productAttr">
                  <div class="productAttr__key">Виробник:</div>
                  <div class="productAttr__value">GIFF PRIME</div>
                  <div class="productAttr__key">Одиниця виміру:</div>
                  <div class="productAttr__value">шт</div>
                </div>
                <div class="productImageBlock__slider">
                  <div class="js-productImage" data-src="https://cdn.example.com/kronas/image-a.jpg"></div>
                  <div class="js-productImage" data-src="https://www.youtube.com/embed/abc123"></div>
                  <div class="js-productImage" data-src="https://cdn.example.com/kronas/image-b.jpg"></div>
                  <div class="js-productImage" data-src="https://cdn.example.com/kronas/image-c.jpg"></div>
                </div>
              </body>
            </html>
        """

        with patch.object(
            parser,
            "_fetch_html",
            new=AsyncMock(return_value=(200, "https://kronas.com.ua/furnitura-270/product", kronas_html)),
        ):
            result = await parser.parse_fitting_source_metadata(
                "https://kronas.com.ua/furnitura-270/petli-i-komplektuyushhie-334/petli-dlya-dsp-454/petli-plavnogo-zakryvaniya-351/petlja-nakladnaja-c-dovodchikom-clip-on-3d-giff-prime-d35-h0-chernyj-nikel",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["source_site"], "kronas")
        self.assertEqual(result["article"], "134376")
        self.assertEqual(result["brand"], "GIFF PRIME")
        self.assertEqual(result["price"], 71.77)
        self.assertEqual(result["currency"], "UAH")
        self.assertEqual(result["unit"], "шт")
        self.assertEqual(result["availability"], "В наявності")
        self.assertEqual(
            result["image_urls"],
            [
                "https://cdn.example.com/kronas/image-a.jpg",
                "https://cdn.example.com/kronas/image-b.jpg",
                "https://cdn.example.com/kronas/image-c.jpg",
            ],
        )
        self.assertNotIn("youtube", " ".join(result["image_urls"]).lower())
        self.assertEqual(result["image_url"], "https://cdn.example.com/kronas/image-a.jpg")

    async def test_source_preview_extracts_viyar_characteristics(self) -> None:
        viyar_html = """
            <html>
              <head>
                <title>Дюбель під запресовку під Mfix Muller</title>
                <meta property="og:image" content="https://cdn.example.com/viyar/image.jpg">
              </head>
              <body>
                <h1 class="text text-weight-dark">Дюбель під запресовку під Mfix Muller</h1>
                <span class="text-code text-weight-bolder">86494</span>
                <span id="product_price">5.52</span>
                <section id="characteristics">
                  <table>
                    <tbody>
                      <tr class="vr-block-char__tr">
                        <td class="vr-block-char__name">Тип товару:</td>
                        <td class="vr-block-char__value">Дюбелі</td>
                      </tr>
                      <tr class="vr-block-char__tr">
                        <td class="vr-block-char__name">Тип стяжки:</td>
                        <td class="vr-block-char__value">Ексцентрикова стяжка</td>
                      </tr>
                      <tr class="vr-block-char__tr">
                        <td class="vr-block-char__name">Виробник:</td>
                        <td class="vr-block-char__value">Muller</td>
                      </tr>
                      <tr class="vr-block-char__tr">
                        <td class="vr-block-char__name">Країна виробник:</td>
                        <td class="vr-block-char__value">Італія</td>
                      </tr>
                      <tr class="vr-block-char__tr">
                        <td class="vr-block-char__name">Колір:</td>
                        <td class="vr-block-char__value">Цинк</td>
                      </tr>
                    </tbody>
                  </table>
                </section>
              </body>
            </html>
        """

        with patch.object(
            parser,
            "_fetch_html",
            new=AsyncMock(return_value=(200, "https://viyar.ua/ua/catalog/dyubel_pod_zapressovku_pod_mfix_muller/", viyar_html)),
        ):
            result = await parser.parse_fitting_source_metadata(
                "https://viyar.ua/ua/catalog/dyubel_pod_zapressovku_pod_mfix_muller/",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["article"], "86494")
        self.assertEqual(result["brand"], "Muller")
        self.assertEqual(result["image_url"], "https://cdn.example.com/viyar/image.jpg")
        self.assertEqual(len(result["characteristics"]), 5)
        self.assertEqual(result["characteristics"]["Тип товару"], "Дюбелі")
        self.assertEqual(result["characteristics"]["Виробник"], "Muller")

    async def test_source_preview_extracts_mt_characteristics(self) -> None:
        mt_html = """
            <html>
              <head>
                <title>CLIP top BLUMOTION спеціальна завіса 110°, накладна, чашка завіси: під саморізи</title>
                <meta itemprop="sku" content="092799">
                <meta itemprop="price" content="138.80">
                <meta itemprop="priceCurrency" content="UAH">
                <meta itemprop="availability" content="https://schema.org/InStock">
                <meta property="og:image" content="https://cdn.example.com/mt/image.jpg">
              </head>
              <body>
                <h1>CLIP top BLUMOTION спеціальна завіса 110°, накладна, чашка завіси: під саморізи</h1>
                <div class="product-page-price">
                  <span class="product-page-price__current">138.80 грн/шт</span>
                  <span class="product-page-price__old">175.70 грн/шт</span>
                </div>
                <div class="productLabel">В наявності</div>
                <div class="promo-note">19</div>
                <section id="product-tab-chars">
                  <div class="product-characteristics">
                    <table>
                      <tbody>
                        <tr>
                          <td>Система завіс</td>
                          <td>CLIP top BLUMOTION</td>
                        </tr>
                        <tr>
                          <td>Ø чашки завіси, мм</td>
                          <td>35</td>
                        </tr>
                        <tr>
                          <td>Кріплення завіс</td>
                          <td>гвинт</td>
                        </tr>
                        <tr>
                          <td>Конструкція завіс</td>
                          <td>накладна</td>
                        </tr>
                        <tr>
                          <td>Кут відкривання завіси, °</td>
                          <td>110</td>
                        </tr>
                        <tr>
                          <td>Наявність пружини</td>
                          <td>з пружиною</td>
                        </tr>
                        <tr>
                          <td>Колір</td>
                          <td>нікель</td>
                        </tr>
                        <tr>
                          <td>Вид завіси</td>
                          <td>стандартна</td>
                        </tr>
                        <tr>
                          <td>Бренд</td>
                          <td>BLUM</td>
                        </tr>
                        <tr>
                          <td>Колір</td>
                          <td>нікель</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </section>
              </body>
            </html>
        """

        with patch("services.fitting_source_parser.Path.exists", return_value=True), patch(
            "services.fitting_source_parser.Path.read_text",
            return_value="{}",
        ), patch.object(
            parser,
            "_fetch_html_with_browser",
            new=AsyncMock(
                return_value=(
                    "https://mt.ua/products/petlya-clip-top-blumotion-110-nakladnaya-specialnaya-40544",
                    mt_html,
                ),
            ),
        ):
            result = await parser.parse_fitting_source_metadata(
                "https://mt.ua/products/petlya-clip-top-blumotion-110-nakladnaya-specialnaya-40544",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["source_site"], "mt")
        self.assertEqual(result["article"], "092799")
        self.assertEqual(result["price"], 138.8)
        self.assertNotEqual(result["price"], 175.7)
        self.assertNotEqual(result["price"], 19.0)
        self.assertEqual(result["currency"], "UAH")
        self.assertEqual(result["unit"], "шт")
        self.assertEqual(result["availability"], "in stock")
        self.assertEqual(result["brand"], "BLUM")
        self.assertEqual(result["image_url"], "https://cdn.example.com/mt/image.jpg")
        self.assertEqual(len(result["characteristics"]), 9)
        self.assertEqual(result["characteristics"]["Система завіс"], "CLIP top BLUMOTION")
        self.assertEqual(result["characteristics"]["Кут відкривання завіси, °"], "110")
        self.assertEqual(result["characteristics"]["Бренд"], "BLUM")
