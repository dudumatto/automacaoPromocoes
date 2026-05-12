from __future__ import annotations

from src.config.stores import STORES, StoreConfig
from src.scrapers.base import BaseStoreScraper
from src.scrapers.stores import (
    AliExpressBrasilScraper,
    AmazonBrasilScraper,
    KabumScraper,
    MagaluScraper,
    MercadoLivreScraper,
    PichauScraper,
    TerabyteScraper,
)


SCRAPER_CLASSES: dict[str, type[BaseStoreScraper]] = {
    "kabum": KabumScraper,
    "pichau": PichauScraper,
    "terabyte": TerabyteScraper,
    "amazon_br": AmazonBrasilScraper,
    "mercado_livre": MercadoLivreScraper,
    "magalu": MagaluScraper,
    "aliexpress_br": AliExpressBrasilScraper,
}

PLAYWRIGHT_FALLBACK_STORE_KEYS = {"pichau", "amazon_br", "magalu"}


def build_scrapers(
    timeout_seconds: int,
    enable_playwright_fallback: bool,
    max_retries: int = 2,
) -> list[BaseStoreScraper]:
    scrapers: list[BaseStoreScraper] = []
    for store in STORES:
        scraper_class = SCRAPER_CLASSES.get(store.key, BaseStoreScraper)
        scrapers.append(
            scraper_class(
                store=store,
                timeout_seconds=timeout_seconds,
                enable_playwright_fallback=(
                    enable_playwright_fallback
                    and store.key in PLAYWRIGHT_FALLBACK_STORE_KEYS
                ),
                max_retries=max_retries,
            )
        )
    return scrapers


def build_scraper(
    store: StoreConfig,
    timeout_seconds: int,
    enable_playwright_fallback: bool,
    max_retries: int = 2,
) -> BaseStoreScraper:
    scraper_class = SCRAPER_CLASSES.get(store.key, BaseStoreScraper)
    return scraper_class(
        store=store,
        timeout_seconds=timeout_seconds,
        enable_playwright_fallback=(
            enable_playwright_fallback and store.key in PLAYWRIGHT_FALLBACK_STORE_KEYS
        ),
        max_retries=max_retries,
    )


def store_by_name(name: str) -> StoreConfig:
    for store in STORES:
        if store.name == name:
            return store
    raise KeyError(f"Loja nao configurada: {name}")


def store_by_key_or_name(value: str) -> StoreConfig:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "amazon": "amazon_br",
        "amazon_brasil": "amazon_br",
        "mercadolivre": "mercado_livre",
        "mercado_livre": "mercado_livre",
        "magazine_luiza": "magalu",
        "magalu": "magalu",
    }
    target = aliases.get(normalized, normalized)
    for store in STORES:
        name_key = store.name.strip().lower().replace(" ", "_")
        if store.key == target or name_key == target:
            return store
    raise KeyError(f"Loja nao configurada: {value}")
