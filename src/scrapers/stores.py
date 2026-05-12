from __future__ import annotations

from src.scrapers.base import BaseStoreScraper, ScraperSelectors


class KabumScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card='[class*="productCard"], [data-testid*="productCard"], article',
        title='[class*="nameCard"], [data-testid*="name"], h2, h3',
        price='[class*="priceCard"], [data-testid*="price"], [class*="price"]',
        link="a[href]",
        old_price='[class*="oldPrice"], [class*="priceOld"], s',
    )


class PichauScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card='[class*="MuiCard"], [class*="product"], article',
        title='h2, h3, [class*="title"], [class*="name"]',
        price='[class*="price"], [class*="Price"], strong',
        link="a[href]",
        old_price='s, [class*="old"], [class*="Old"]',
    )


class TerabyteScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card='.commerce_columns_item, [class*="product"], article',
        title='.prod-name, h2, h3, [class*="name"]',
        price='.prod-new-price, [class*="price"], strong',
        link="a[href]",
        old_price='s, .prod-old-price, [class*="old"]',
    )


class AmazonBrasilScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card='[data-component-type="s-search-result"]',
        title="h2 span",
        price=".a-price .a-offscreen",
        link="a.a-link-normal[href]",
        old_price=".a-price.a-text-price .a-offscreen",
        marketplace=".a-row.a-size-base.a-color-secondary",
    )


class MercadoLivreScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card='.ui-search-result__wrapper, .ui-search-layout__item, [class*="poly-card"]',
        title='.poly-component__title, .ui-search-item__title, h2, h3',
        price='.andes-money-amount, .price-tag, [class*="price"]',
        link="a[href]",
        old_price='s, .andes-money-amount--previous, [class*="previous"]',
        marketplace='.ui-search-official-store-label, [class*="seller"]',
    )


class MagaluScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card='[data-testid="product-card-container"], [class*="product"], article',
        title='[data-testid="product-title"], h2, h3, [class*="title"]',
        price='[data-testid="price-value"], [class*="price"], strong',
        link="a[href]",
        old_price='s, [data-testid*="original"], [class*="old"]',
        marketplace='[data-testid*="seller"], [class*="seller"]',
    )


class AliExpressBrasilScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card='[class*="search-item"], [class*="product"], [class*="card"], article',
        title='h1, h2, h3, [class*="title"], [class*="name"]',
        price='[class*="price"], [class*="Price"]',
        link="a[href]",
        old_price='s, [class*="old"], [class*="original"]',
        marketplace='[class*="store"], [class*="seller"]',
    )

