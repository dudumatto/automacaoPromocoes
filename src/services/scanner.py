from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from src.config.keywords import INITIAL_KEYWORDS
from src.config.settings import Settings
from src.database.connection import Database
from src.database.repository import RadarRepository
from src.notifiers.discord import DealAlert, DiscordNotifier
from src.scrapers.base import ProductOffer, ScraperErrorKind
from src.scrapers.registry import build_scrapers
from src.services.scoring import score_offer


@dataclass(frozen=True)
class ScanSummary:
    products_seen: int
    deals_found: int
    alerts_sent: int
    errors: list[str]
    elapsed_seconds: float
    ok_stores: list[str] = field(default_factory=list)
    error_counts_by_store: dict[str, dict[str, int]] = field(default_factory=dict)

    def stores_by_error_kind(self, kind: ScraperErrorKind) -> dict[str, int]:
        grouped: dict[str, int] = {}
        for store, counts in self.error_counts_by_store.items():
            count = counts.get(kind.value, 0)
            if count:
                grouped[store] = count
        return grouped


class DealScanner:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        notifier: DiscordNotifier,
    ) -> None:
        self.settings = settings
        self.repository = RadarRepository(db)
        self.notifier = notifier
        self.scrapers = build_scrapers(
            timeout_seconds=settings.request_timeout_seconds,
            enable_playwright_fallback=settings.enable_playwright_fallback,
            max_retries=settings.max_retries,
        )

    def scan(self) -> ScanSummary:
        scan_started_at = time.perf_counter()
        products_seen = 0
        deals_found = 0
        alerts_sent = 0
        errors: list[str] = []
        error_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        ok_stores: list[str] = []

        for scraper in self.scrapers:
            store_started_at = time.perf_counter()
            store_had_error = False
            store_id = self.repository.upsert_store(scraper.store)
            self._log(f"[loja] {scraper.store.name}")
            for keyword in INITIAL_KEYWORDS:
                result = scraper.search_with_diagnostics(
                    keyword=keyword,
                    limit=self.settings.max_results_per_store,
                )
                self._log_keyword_result(result)
                if result.error_kind:
                    store_had_error = True
                    error_counts[scraper.store.name][result.error_kind.value] += 1
                    errors.append(
                        f"{scraper.store.name} / {keyword}: {result.error_message}"
                    )
                    continue

                for offer in result.offers:
                    products_seen += 1
                    product_id = self.repository.upsert_product(offer, store_id)
                    self.repository.insert_price_history(product_id, offer)
                    estimated_average = self.estimate_average_price(product_id, offer)
                    if not estimated_average or estimated_average <= offer.current_price:
                        continue

                    score = score_offer(
                        offer=offer,
                        store=scraper.store,
                        estimated_average_price=estimated_average,
                        min_discount_percent=self.settings.min_discount_percent,
                        min_score=self.settings.min_score,
                    )
                    if not score.should_alert:
                        continue
                    if self.repository.has_recent_similar_deal(product_id, offer.current_price):
                        continue

                    deal_id = self.repository.insert_deal(
                        product_id=product_id,
                        current_price=offer.current_price,
                        estimated_avg_price=estimated_average,
                        discount_percent=score.discount_percent,
                        score=score.score,
                        alert_reason=score.reason,
                        verdict=score.verdict,
                    )
                    deals_found += 1
                    if self.notifier.send_deal_alert(
                        DealAlert(
                            offer=offer,
                            estimated_average_price=estimated_average,
                            discount_percent=score.discount_percent,
                            score=score.score,
                            verdict=score.verdict,
                            reason=score.reason,
                        )
                    ):
                        self.repository.mark_deal_notified(deal_id)
                        alerts_sent += 1
            store_elapsed = time.perf_counter() - store_started_at
            if not store_had_error:
                ok_stores.append(scraper.store.name)
            self._log(f"[loja] {scraper.store.name} tempo={store_elapsed:.1f}s")

        return ScanSummary(
            products_seen=products_seen,
            deals_found=deals_found,
            alerts_sent=alerts_sent,
            errors=errors,
            elapsed_seconds=time.perf_counter() - scan_started_at,
            ok_stores=ok_stores,
            error_counts_by_store={
                store: dict(counts) for store, counts in error_counts.items()
            },
        )

    def estimate_average_price(self, product_id: int, offer: ProductOffer) -> float | None:
        history_average = self.repository.average_price_before_current(product_id)
        candidates = []
        if history_average:
            candidates.append(history_average)
        if offer.listed_original_price and offer.listed_original_price > offer.current_price:
            candidates.append(offer.listed_original_price)
        if not candidates:
            return None
        return max(candidates)

    def send_test_alert(self) -> None:
        offer = ProductOffer(
            name="Monitor Gamer 27 165Hz IPS 1ms",
            category="monitor",
            store="Kabum",
            current_price=899.90,
            listed_original_price=1399.90,
            url="https://www.kabum.com.br/",
            keyword="monitor 165hz",
            source="test-alert",
        )
        sent = self.notifier.send_deal_alert(
            DealAlert(
                offer=offer,
                estimated_average_price=1399.90,
                discount_percent=35.7,
                score=88,
                verdict="Promocao forte",
                reason="Alerta de teste do Radar Setup; nenhum segredo foi salvo no codigo.",
            )
        )
        if not sent:
            print("Nenhum webhook Discord aplicavel configurado. Preview do alerta:")
            print("- Produto: Monitor Gamer 27 165Hz IPS 1ms")
            print("- Preco atual: R$ 899,90")
            print("- Queda: 35.7%")
            print("- Loja: Kabum")
            print("- Score: 88")

    def _log(self, message: str) -> None:
        if self.settings.verbose_logs:
            print(message)

    def _log_keyword_result(self, result: object) -> None:
        if not self.settings.verbose_logs:
            return
        status = getattr(result, "status_code", None)
        status_text = status if status is not None else "sem-status"
        parts = [
            f"[keyword] loja={getattr(result, 'store_name')}",
            f"keyword={getattr(result, 'keyword')!r}",
            f"url={getattr(result, 'url')}",
            f"status={status_text}",
            f"cards={getattr(result, 'card_count')}",
            f"produtos={len(getattr(result, 'offers'))}",
            f"fonte={getattr(result, 'source')}",
            f"tempo={getattr(result, 'elapsed_seconds'):.1f}s",
        ]
        error_kind = getattr(result, "error_kind")
        if error_kind:
            parts.append(f"erro={error_kind.value}")
            parts.append(f"motivo={getattr(result, 'error_message')}")
        print(" | ".join(parts))
