from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoreConfig:
    key: str
    name: str
    base_url: str
    search_url: str
    trust_score: int
    marketplace_risk: int = 0


STORES = [
    StoreConfig(
        key="kabum",
        name="Kabum",
        base_url="https://www.kabum.com.br",
        search_url="https://www.kabum.com.br/busca/{query}",
        trust_score=95,
    ),
    StoreConfig(
        key="pichau",
        name="Pichau",
        base_url="https://www.pichau.com.br",
        search_url="https://www.pichau.com.br/search?q={query}",
        trust_score=90,
    ),
    StoreConfig(
        key="terabyte",
        name="Terabyte",
        base_url="https://www.terabyteshop.com.br",
        search_url="https://www.terabyteshop.com.br/busca?str={query}",
        trust_score=90,
    ),
    StoreConfig(
        key="amazon_br",
        name="Amazon Brasil",
        base_url="https://www.amazon.com.br",
        search_url="https://www.amazon.com.br/s?k={query}",
        trust_score=85,
        marketplace_risk=5,
    ),
    StoreConfig(
        key="mercado_livre",
        name="Mercado Livre",
        base_url="https://www.mercadolivre.com.br",
        search_url="https://lista.mercadolivre.com.br/{query}",
        trust_score=78,
        marketplace_risk=12,
    ),
    StoreConfig(
        key="magalu",
        name="Magazine Luiza",
        base_url="https://www.magazineluiza.com.br",
        search_url="https://www.magazineluiza.com.br/busca/{query}/",
        trust_score=84,
        marketplace_risk=8,
    ),
    StoreConfig(
        key="aliexpress_br",
        name="AliExpress Brasil",
        base_url="https://pt.aliexpress.com",
        search_url="https://pt.aliexpress.com/w/wholesale-{query}.html",
        trust_score=70,
        marketplace_risk=18,
    ),
]

