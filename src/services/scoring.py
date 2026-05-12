from __future__ import annotations

from dataclasses import dataclass

from src.config.stores import StoreConfig
from src.scrapers.base import ProductOffer


@dataclass(frozen=True)
class ScoreResult:
    discount_percent: float
    score: int
    verdict: str
    reason: str
    should_alert: bool


def calculate_discount(current_price: float, average_price: float) -> float:
    if average_price <= 0 or current_price <= 0:
        return 0.0
    return max(0.0, ((average_price - current_price) / average_price) * 100)


def classify_discount(discount_percent: float) -> tuple[int, str]:
    if discount_percent < 20:
        return 0, "Ignorar"
    if discount_percent < 30:
        return 65, "Promocao comum"
    if discount_percent < 40:
        return 80, "Promocao forte"
    return 95, "Promocao absurda"


def score_offer(
    offer: ProductOffer,
    store: StoreConfig,
    estimated_average_price: float,
    min_discount_percent: float,
    min_score: int,
) -> ScoreResult:
    discount = calculate_discount(offer.current_price, estimated_average_price)
    base_score, verdict = classify_discount(discount)

    if discount < 20:
        return ScoreResult(
            discount_percent=discount,
            score=0,
            verdict=verdict,
            reason=f"Queda de {discount:.1f}% abaixo do minimo de 20%.",
            should_alert=False,
        )

    trust_bonus = round((store.trust_score - 80) * 0.5)
    marketplace_penalty = store.marketplace_risk
    if offer.is_marketplace:
        marketplace_penalty += 10
    if offer.marketplace_name:
        marketplace_penalty += 5

    discount_bonus = min(8, max(0, round(discount - 20)))
    score = max(0, min(100, base_score + trust_bonus + discount_bonus - marketplace_penalty))

    reason_parts = [
        f"Preco {discount:.1f}% abaixo da media estimada",
        f"loja com confianca {store.trust_score}/100",
    ]
    if marketplace_penalty:
        reason_parts.append(f"penalidade marketplace/seller {marketplace_penalty} pts")
    if offer.listed_original_price:
        reason_parts.append("media reforcada por preco original listado")
    if offer.shipping_price:
        reason_parts.append(f"frete considerado no preco final: R$ {offer.shipping_price:.2f}")
    if offer.tax_price:
        reason_parts.append(f"imposto/taxa considerado no preco final: R$ {offer.tax_price:.2f}")

    should_alert = discount >= min_discount_percent and score >= min_score
    return ScoreResult(
        discount_percent=discount,
        score=score,
        verdict=verdict,
        reason="; ".join(reason_parts) + ".",
        should_alert=should_alert,
    )
