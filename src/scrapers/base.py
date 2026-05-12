from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Iterable
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from src.config.keywords import CATEGORY_ALIASES
from src.config.stores import StoreConfig
from src.scrapers.utils import parse_labeled_price, parse_price


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Connection": "keep-alive",
}


@dataclass(frozen=True)
class ProductOffer:
    name: str
    category: str
    store: str
    current_price: float
    url: str
    keyword: str
    source: str
    listed_original_price: float | None = None
    marketplace_name: str | None = None
    is_marketplace: bool = False
    shipping_price: float | None = None
    tax_price: float | None = None


@dataclass(frozen=True)
class ScraperSelectors:
    card: str
    title: str
    price: str
    link: str
    old_price: str | None = None
    marketplace: str | None = None


class ScraperErrorKind(str, Enum):
    BLOCKED = "BLOCKED"
    TEMPORARY_UNAVAILABLE = "TEMPORARY_UNAVAILABLE"
    HTTP_ERROR = "HTTP_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    PARSE_ERROR = "PARSE_ERROR"


@dataclass(frozen=True)
class ScraperError(Exception):
    kind: ScraperErrorKind
    message: str
    status_code: int | None = None
    url: str = ""

    def __str__(self) -> str:
        status = f" HTTP {self.status_code}" if self.status_code else ""
        return f"{self.kind.value}{status}: {self.message}"


@dataclass(frozen=True)
class ScraperSearchResult:
    store_name: str
    store_key: str
    keyword: str
    url: str
    status_code: int | None
    offers: list[ProductOffer]
    elapsed_seconds: float
    source: str
    card_count: int
    error_kind: ScraperErrorKind | None = None
    error_message: str = ""
    html: str = ""

    @property
    def ok(self) -> bool:
        return self.error_kind is None


class BaseStoreScraper:
    selectors: ScraperSelectors | None = None

    def __init__(
        self,
        store: StoreConfig,
        timeout_seconds: int = 20,
        enable_playwright_fallback: bool = False,
        max_retries: int = 2,
    ) -> None:
        self.store = store
        self.timeout_seconds = timeout_seconds
        self.enable_playwright_fallback = enable_playwright_fallback
        self.max_retries = max(0, max_retries)

    def search(self, keyword: str, limit: int = 5) -> list[ProductOffer]:
        return self.search_with_diagnostics(keyword=keyword, limit=limit).offers

    def search_with_diagnostics(
        self,
        keyword: str,
        limit: int = 5,
        include_html: bool = False,
    ) -> ScraperSearchResult:
        started_at = time.perf_counter()
        url = self.search_url(keyword)
        status_code: int | None = None
        source = "http"
        html = ""
        try:
            html, status_code, source = self.fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")

            offers = self.parse_json_ld(soup, keyword)
            offers.extend(self.parse_cards(soup, keyword))
            unique_offers = self.unique_offers(offers)[:limit]
            return ScraperSearchResult(
                store_name=self.store.name,
                store_key=self.store.key,
                keyword=keyword,
                url=url,
                status_code=status_code,
                offers=unique_offers,
                elapsed_seconds=time.perf_counter() - started_at,
                source=source,
                card_count=self.count_cards(soup),
                html=html if include_html else "",
            )
        except ScraperError as exc:
            return ScraperSearchResult(
                store_name=self.store.name,
                store_key=self.store.key,
                keyword=keyword,
                url=url,
                status_code=exc.status_code or status_code,
                offers=[],
                elapsed_seconds=time.perf_counter() - started_at,
                source=source,
                card_count=0,
                error_kind=exc.kind,
                error_message=str(exc),
                html=html if include_html else "",
            )
        except Exception as exc:
            return ScraperSearchResult(
                store_name=self.store.name,
                store_key=self.store.key,
                keyword=keyword,
                url=url,
                status_code=status_code,
                offers=[],
                elapsed_seconds=time.perf_counter() - started_at,
                source=source,
                card_count=0,
                error_kind=ScraperErrorKind.PARSE_ERROR,
                error_message=f"{type(exc).__name__}: {exc}",
                html=html if include_html else "",
            )

    def search_url(self, keyword: str) -> str:
        query = quote_plus(keyword)
        return self.store.search_url.format(query=query)

    def fetch_html(self, url: str) -> tuple[str, int | None, str]:
        last_error: requests.RequestException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(
                    url,
                    headers=REQUEST_HEADERS,
                    timeout=self.timeout_seconds,
                )
                status_code = response.status_code
                if status_code == 403:
                    return self._fetch_or_raise_blocked(url, status_code)
                if status_code == 503:
                    if attempt < self.max_retries:
                        time.sleep(0.75 * (attempt + 1))
                        continue
                    return self._fetch_or_raise_temporary(url, status_code)
                if status_code >= 400:
                    raise ScraperError(
                        kind=ScraperErrorKind.HTTP_ERROR,
                        message=f"Resposta HTTP inesperada da loja: {status_code}",
                        status_code=status_code,
                        url=url,
                    )
                if response.text.strip():
                    return response.text, status_code, "http"
                raise ScraperError(
                    kind=ScraperErrorKind.HTTP_ERROR,
                    message="Resposta HTTP vazia.",
                    status_code=status_code,
                    url=url,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.75 * (attempt + 1))
                    continue

        if self.enable_playwright_fallback:
            try:
                html, status_code = self.fetch_html_with_playwright(url)
                return html, status_code, "playwright"
            except Exception as fallback_exc:
                message = (
                    f"Falha de rede apos retries: {last_error}; "
                    f"Playwright fallback falhou: {fallback_exc}"
                )
        else:
            message = f"Falha de rede apos retries: {last_error}"
        raise ScraperError(
            kind=ScraperErrorKind.NETWORK_ERROR,
            message=message,
            url=url,
        )

    def _fetch_or_raise_blocked(self, url: str, status_code: int) -> tuple[str, int | None, str]:
        if self.enable_playwright_fallback:
            try:
                html, fallback_status = self.fetch_html_with_playwright(url)
                self._raise_for_fallback_status(
                    url=url,
                    status_code=fallback_status,
                    blocked_message="Loja bloqueou scraping HTTP 403 mesmo com Playwright.",
                )
                return html, fallback_status or status_code, "playwright"
            except ScraperError:
                raise
            except Exception as exc:
                message = f"Loja bloqueou scraping HTTP 403; Playwright fallback falhou: {exc}"
        else:
            message = "Loja bloqueou scraping HTTP 403."
        raise ScraperError(
            kind=ScraperErrorKind.BLOCKED,
            message=message,
            status_code=status_code,
            url=url,
        )

    def _fetch_or_raise_temporary(
        self, url: str, status_code: int
    ) -> tuple[str, int | None, str]:
        if self.enable_playwright_fallback:
            try:
                html, fallback_status = self.fetch_html_with_playwright(url)
                self._raise_for_fallback_status(
                    url=url,
                    status_code=fallback_status,
                    blocked_message=(
                        "Loja retornou bloqueio HTTP 403 no fallback Playwright."
                    ),
                )
                return html, fallback_status or status_code, "playwright"
            except ScraperError:
                raise
            except Exception as exc:
                message = (
                    "Loja retornou HTTP 503 apos retries; "
                    f"Playwright fallback falhou: {exc}"
                )
        else:
            message = "Loja retornou HTTP 503 apos retries."
        raise ScraperError(
            kind=ScraperErrorKind.TEMPORARY_UNAVAILABLE,
            message=message,
            status_code=status_code,
            url=url,
        )

    def _raise_for_fallback_status(
        self,
        *,
        url: str,
        status_code: int | None,
        blocked_message: str,
    ) -> None:
        if status_code is None or status_code < 400:
            return
        if status_code == 403:
            raise ScraperError(
                kind=ScraperErrorKind.BLOCKED,
                message=blocked_message,
                status_code=status_code,
                url=url,
            )
        if status_code == 503:
            raise ScraperError(
                kind=ScraperErrorKind.TEMPORARY_UNAVAILABLE,
                message="Loja retornou HTTP 503 no fallback Playwright.",
                status_code=status_code,
                url=url,
            )
        raise ScraperError(
            kind=ScraperErrorKind.HTTP_ERROR,
            message=f"Fallback Playwright retornou HTTP {status_code}.",
            status_code=status_code,
            url=url,
        )

    def fetch_html_with_playwright(self, url: str) -> tuple[str, int | None]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(extra_http_headers=REQUEST_HEADERS)
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout_seconds * 1000,
            )
            page.wait_for_timeout(1500)
            content = page.content()
            status_code = response.status if response else None
            browser.close()
            return content, status_code

    def count_cards(self, soup: BeautifulSoup) -> int:
        if self.selectors is None:
            return len(soup.select("a[href]"))
        return len(soup.select(self.selectors.card))

    def selector_report(self) -> dict[str, str | None]:
        if self.selectors is None:
            return {
                "card": "a[href]",
                "title": None,
                "price": None,
                "link": "a[href]",
                "old_price": None,
                "marketplace": None,
            }
        return {
            "card": self.selectors.card,
            "title": self.selectors.title,
            "price": self.selectors.price,
            "link": self.selectors.link,
            "old_price": self.selectors.old_price,
            "marketplace": self.selectors.marketplace,
        }

    def parse_json_ld(self, soup: BeautifulSoup, keyword: str) -> list[ProductOffer]:
        offers: list[ProductOffer] = []
        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string or script.get_text(strip=True)
            if not raw:
                continue
            for item in self._iter_json_objects(raw):
                offers.extend(self._offers_from_json_ld_item(item, keyword))
        return offers

    def _iter_json_objects(self, raw: str) -> Iterable[dict]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _offers_from_json_ld_item(self, item: dict, keyword: str) -> list[ProductOffer]:
        candidates: list[dict] = []
        graph = item.get("@graph")
        if isinstance(graph, list):
            candidates.extend(node for node in graph if isinstance(node, dict))
        candidates.append(item)

        offers: list[ProductOffer] = []
        for candidate in candidates:
            if candidate.get("@type") not in {"Product", "Offer"}:
                continue
            name = str(candidate.get("name") or "").strip()
            offer_data = candidate.get("offers", candidate)
            if isinstance(offer_data, list):
                offer_data = offer_data[0] if offer_data else {}
            if not isinstance(offer_data, dict):
                continue
            price = parse_price(str(offer_data.get("price") or ""))
            url = str(candidate.get("url") or offer_data.get("url") or "").strip()
            if not name or price is None or not url:
                continue
            offers.append(
                ProductOffer(
                    name=name,
                    category=infer_category(name, keyword),
                    store=self.store.name,
                    current_price=price,
                    url=urljoin(self.store.base_url, url),
                    keyword=keyword,
                    source="json-ld",
                    is_marketplace=self.store.marketplace_risk >= 10,
                )
            )
        return offers

    def parse_cards(self, soup: BeautifulSoup, keyword: str) -> list[ProductOffer]:
        if self.selectors is None:
            return self.parse_generic_cards(soup, keyword)

        offers: list[ProductOffer] = []
        for card in soup.select(self.selectors.card):
            title_el = card.select_one(self.selectors.title)
            price_el = card.select_one(self.selectors.price)
            link_el = card.select_one(self.selectors.link)
            if not title_el or not price_el or not link_el:
                continue

            name = title_el.get_text(" ", strip=True)
            price = parse_price(price_el.get_text(" ", strip=True))
            href = link_el.get("href")
            if not name or price is None or not href:
                continue
            card_text = card.get_text(" ", strip=True)
            shipping_price = parse_labeled_price(
                card_text,
                ["frete", "envio", "shipping"],
            )
            tax_price = parse_labeled_price(
                card_text,
                ["imposto", "taxa de importacao", "import tax", "tax"],
            )
            effective_price = price + (shipping_price or 0.0) + (tax_price or 0.0)

            old_price = None
            if self.selectors.old_price:
                old_price_el = card.select_one(self.selectors.old_price)
                if old_price_el:
                    old_price = parse_price(old_price_el.get_text(" ", strip=True))

            marketplace_name = None
            if self.selectors.marketplace:
                marketplace_el = card.select_one(self.selectors.marketplace)
                if marketplace_el:
                    marketplace_name = marketplace_el.get_text(" ", strip=True)

            offers.append(
                ProductOffer(
                    name=name,
                    category=infer_category(name, keyword),
                    store=self.store.name,
                    current_price=effective_price,
                    url=urljoin(self.store.base_url, str(href)),
                    keyword=keyword,
                    source="css-card",
                    listed_original_price=old_price,
                    marketplace_name=marketplace_name,
                    is_marketplace=bool(marketplace_name) or self.store.marketplace_risk >= 10,
                    shipping_price=shipping_price,
                    tax_price=tax_price,
                )
            )
        return offers

    def parse_generic_cards(self, soup: BeautifulSoup, keyword: str) -> list[ProductOffer]:
        offers: list[ProductOffer] = []
        for link in soup.select("a[href]"):
            text = link.get_text(" ", strip=True)
            price = parse_price(text)
            if price is None:
                continue
            name = text.split("R$")[0].strip()[:180]
            if len(name) < 8:
                continue
            href = link.get("href")
            offers.append(
                ProductOffer(
                    name=name,
                    category=infer_category(name, keyword),
                    store=self.store.name,
                    current_price=price,
                    url=urljoin(self.store.base_url, str(href)),
                    keyword=keyword,
                    source="generic-link",
                    is_marketplace=self.store.marketplace_risk >= 10,
                )
            )
        return offers

    def unique_offers(self, offers: list[ProductOffer]) -> list[ProductOffer]:
        seen: set[str] = set()
        unique: list[ProductOffer] = []
        for offer in offers:
            key = offer.url.lower().split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            unique.append(offer)
        return unique


def infer_category(product_name: str, keyword: str) -> str:
    haystack = f"{product_name} {keyword}".lower()
    for category, aliases in CATEGORY_ALIASES.items():
        if any(alias.lower() in haystack for alias in aliases):
            return category
    return "setup"
