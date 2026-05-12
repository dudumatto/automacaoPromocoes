from __future__ import annotations

from src.scrapers.base import ProductOffer


class TelegramNotifier:
    """Placeholder preparado para uma futura integracao com bot do Telegram."""

    def send_deal_alert(
        self,
        offer: ProductOffer,
        estimated_average_price: float,
        discount_percent: float,
        score: int,
        verdict: str,
        reason: str,
    ) -> bool:
        return False

