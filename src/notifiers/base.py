from __future__ import annotations

from typing import Protocol

from src.scrapers.base import ProductOffer


class Notifier(Protocol):
    def send_deal_alert(
        self,
        deal: object | None = None,
        *,
        offer: ProductOffer | None = None,
        estimated_average_price: float | None = None,
        discount_percent: float | None = None,
        score: int | None = None,
        verdict: str | None = None,
        reason: str | None = None,
    ) -> bool:
        ...
