from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.config.settings import Settings
from src.config.stores import StoreConfig
from src.database.connection import Database
from src.database.schema import initialize_database
from src.notifiers.discord import DealAlert, DiscordNotifier
from src.scrapers.base import (
    BaseStoreScraper,
    ProductOffer,
    ScraperErrorKind,
    ScraperSearchResult,
)
from src.scrapers.utils import parse_labeled_price, parse_price
from src.services.scanner import DealScanner, ScanSummary
from src.services.scoring import score_offer


class PriceParsingTests(unittest.TestCase):
    def test_parse_brl_price(self) -> None:
        self.assertEqual(parse_price("R$ 1.299,90"), 1299.90)

    def test_parse_labeled_shipping_and_tax(self) -> None:
        text = "Produto X R$ 900,00 Frete R$ 29,90 Imposto R$ 80,00"

        self.assertEqual(parse_labeled_price(text, ["frete"]), 29.90)
        self.assertEqual(parse_labeled_price(text, ["imposto"]), 80.00)

    def test_parse_free_shipping(self) -> None:
        self.assertEqual(parse_labeled_price("Frete gratis para sua regiao", ["frete"]), 0.0)


class ScoringTests(unittest.TestCase):
    def test_ignores_discount_below_twenty_percent(self) -> None:
        offer = ProductOffer(
            name="SSD NVMe 1TB",
            category="SSD",
            store="Kabum",
            current_price=850.0,
            url="https://example.com/ssd",
            keyword="ssd nvme 1tb",
            source="test",
        )
        store = StoreConfig(
            key="kabum",
            name="Kabum",
            base_url="https://www.kabum.com.br",
            search_url="https://www.kabum.com.br/busca/{query}",
            trust_score=95,
        )

        result = score_offer(offer, store, 1000.0, 25, 70)

        self.assertFalse(result.should_alert)
        self.assertEqual(result.score, 0)

    def test_scores_strong_discount_in_trusted_store(self) -> None:
        offer = ProductOffer(
            name="Monitor 165Hz",
            category="monitor",
            store="Kabum",
            current_price=650.0,
            url="https://example.com/monitor",
            keyword="monitor 165hz",
            source="test",
        )
        store = StoreConfig(
            key="kabum",
            name="Kabum",
            base_url="https://www.kabum.com.br",
            search_url="https://www.kabum.com.br/busca/{query}",
            trust_score=95,
        )

        result = score_offer(offer, store, 1000.0, 25, 70)

        self.assertTrue(result.should_alert)
        self.assertEqual(result.verdict, "Promocao forte")
        self.assertGreaterEqual(result.score, 80)


class DiscordNotifierTests(unittest.TestCase):
    def make_deal(
        self,
        *,
        category: str = "monitor",
        discount_percent: float = 35.7,
        score: int = 88,
    ) -> DealAlert:
        return DealAlert(
            offer=ProductOffer(
                name="Monitor Gamer 27 165Hz",
                category=category,
                store="Kabum",
                current_price=899.90,
                url="https://example.com/produto",
                keyword="monitor 165hz",
                source="test",
            ),
            estimated_average_price=1399.90,
            discount_percent=discount_percent,
            score=score,
            verdict="Promocao forte",
            reason="Teste",
        )

    @patch("src.notifiers.discord.requests.post")
    def test_sends_embed_payload(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None

        sent = DiscordNotifier(
            setup_webhook_url="https://discord.test/setup"
        ).send_deal_alert(self.make_deal())

        self.assertTrue(sent)
        payload = post.call_args.kwargs["json"]
        embed = payload["embeds"][0]
        self.assertTrue(embed["title"].startswith("\U0001F6A8 Promocao forte"))
        self.assertEqual(embed["fields"][1]["value"], "R$ 899,90")
        self.assertEqual(post.call_args.args[0], "https://discord.test/setup")
        self.assertIn("timestamp", embed)

    @patch("src.notifiers.discord.requests.post")
    def test_absurd_deal_goes_to_absurdas_webhook(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None

        sent = DiscordNotifier(
            absurdas_webhook_url="https://discord.test/absurdas"
        ).send_deal_alert(self.make_deal(discount_percent=40.0, score=92))

        self.assertTrue(sent)
        self.assertEqual(post.call_args.args[0], "https://discord.test/absurdas")

    @patch("src.notifiers.discord.requests.post")
    def test_gpu_goes_to_hardware_webhook(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None

        sent = DiscordNotifier(
            hardware_webhook_url="https://discord.test/hardware"
        ).send_deal_alert(self.make_deal(category="GPU"))

        self.assertTrue(sent)
        self.assertEqual(post.call_args.args[0], "https://discord.test/hardware")

    @patch("src.notifiers.discord.requests.post")
    def test_braco_articulado_goes_to_setup_webhook(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None

        sent = DiscordNotifier(
            setup_webhook_url="https://discord.test/setup"
        ).send_deal_alert(self.make_deal(category="braço articulado"))

        self.assertTrue(sent)
        self.assertEqual(post.call_args.args[0], "https://discord.test/setup")

    @patch("src.notifiers.discord.requests.post")
    def test_legacy_fallback_webhook_url_is_used(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None

        sent = DiscordNotifier("https://discord.test/fallback").send_deal_alert(
            self.make_deal(category="GPU")
        )

        self.assertTrue(sent)
        self.assertEqual(post.call_args.args[0], "https://discord.test/fallback")

    @patch("src.notifiers.discord.requests.post")
    def test_empty_webhook_does_not_break(self, post: Mock) -> None:
        sent = DiscordNotifier().send_deal_alert(self.make_deal(category="GPU"))

        self.assertFalse(sent)
        post.assert_not_called()

    @patch("src.notifiers.discord.requests.post")
    def test_duplicate_deal_is_not_sent_twice_to_same_channel(self, post: Mock) -> None:
        post.return_value.raise_for_status.return_value = None
        notifier = DiscordNotifier(hardware_webhook_url="https://discord.test/hardware")
        deal = self.make_deal(category="GPU")

        self.assertTrue(notifier.send_deal_alert(deal))
        self.assertFalse(notifier.send_deal_alert(deal))

        self.assertEqual(post.call_count, 1)


class ScraperErrorHandlingTests(unittest.TestCase):
    def make_scraper(self, *, max_retries: int = 0) -> BaseStoreScraper:
        store = StoreConfig(
            key="fake",
            name="Fake Store",
            base_url="https://example.com",
            search_url="https://example.com/search?q={query}",
            trust_score=80,
        )
        return BaseStoreScraper(store=store, max_retries=max_retries)

    @patch("src.scrapers.base.requests.get")
    def test_http_403_is_classified_as_blocked(self, get: Mock) -> None:
        response = Mock(status_code=403, text="Forbidden")
        get.return_value = response

        result = self.make_scraper().search_with_diagnostics("monitor")

        self.assertEqual(result.error_kind, ScraperErrorKind.BLOCKED)
        self.assertEqual(result.status_code, 403)

    @patch("src.scrapers.base.requests.get")
    def test_http_503_is_classified_as_temporary_unavailable(self, get: Mock) -> None:
        response = Mock(status_code=503, text="Service Unavailable")
        get.return_value = response

        result = self.make_scraper().search_with_diagnostics("monitor")

        self.assertEqual(result.error_kind, ScraperErrorKind.TEMPORARY_UNAVAILABLE)
        self.assertEqual(result.status_code, 503)


class ScanSummaryTests(unittest.TestCase):
    def test_summary_groups_errors_by_store(self) -> None:
        summary = ScanSummary(
            products_seen=0,
            deals_found=0,
            alerts_sent=0,
            errors=[],
            elapsed_seconds=1.0,
            error_counts_by_store={
                "Pichau": {ScraperErrorKind.BLOCKED.value: 2},
                "Amazon Brasil": {
                    ScraperErrorKind.TEMPORARY_UNAVAILABLE.value: 1
                },
            },
        )

        self.assertEqual(
            summary.stores_by_error_kind(ScraperErrorKind.BLOCKED),
            {"Pichau": 2},
        )
        self.assertEqual(
            summary.stores_by_error_kind(ScraperErrorKind.TEMPORARY_UNAVAILABLE),
            {"Amazon Brasil": 1},
        )


class ScannerContinuationTests(unittest.TestCase):
    def make_settings(self, database_url: str) -> Settings:
        return Settings(
            discord_webhook_url="",
            discord_webhook_hardware="",
            discord_webhook_setup="",
            discord_webhook_absurdas="",
            database_url=database_url,
            min_discount_percent=25,
            min_score=70,
            request_timeout_seconds=1,
            max_results_per_store=5,
            enable_playwright_fallback=False,
            max_retries=0,
            verbose_logs=False,
        )

    def test_scan_continues_when_store_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite3"
            db = Database(db_path)
            initialize_database(db)
            scanner = DealScanner(
                db=db,
                settings=self.make_settings(f"sqlite:///{db_path}"),
                notifier=Mock(send_deal_alert=Mock(return_value=False)),
            )
            scanner.scrapers = [
                FakeScraper(
                    store=StoreConfig(
                        key="pichau",
                        name="Pichau",
                        base_url="https://www.pichau.com.br",
                        search_url="https://www.pichau.com.br/search?q={query}",
                        trust_score=90,
                    ),
                    results=[
                        ScraperSearchResult(
                            store_name="Pichau",
                            store_key="pichau",
                            keyword="monitor 144hz",
                            url="https://www.pichau.com.br/search?q=monitor",
                            status_code=403,
                            offers=[],
                            elapsed_seconds=0.01,
                            source="http",
                            card_count=0,
                            error_kind=ScraperErrorKind.BLOCKED,
                            error_message="BLOCKED HTTP 403",
                        )
                    ],
                ),
                FakeScraper(
                    store=StoreConfig(
                        key="kabum",
                        name="Kabum",
                        base_url="https://www.kabum.com.br",
                        search_url="https://www.kabum.com.br/busca/{query}",
                        trust_score=95,
                    ),
                    results=[
                        ScraperSearchResult(
                            store_name="Kabum",
                            store_key="kabum",
                            keyword="monitor 144hz",
                            url="https://www.kabum.com.br/busca/monitor",
                            status_code=200,
                            offers=[
                                ProductOffer(
                                    name="Monitor 144Hz",
                                    category="monitor",
                                    store="Kabum",
                                    current_price=999.0,
                                    url="https://example.com/monitor",
                                    keyword="monitor 144hz",
                                    source="test",
                                )
                            ],
                            elapsed_seconds=0.01,
                            source="http",
                            card_count=1,
                        )
                    ],
                ),
            ]

            summary = scanner.scan()

            self.assertEqual(summary.products_seen, 1)
            self.assertEqual(
                summary.stores_by_error_kind(ScraperErrorKind.BLOCKED),
                {"Pichau": 1},
            )


class FakeScraper:
    def __init__(self, store: StoreConfig, results: list[ScraperSearchResult]) -> None:
        self.store = store
        self.results = results
        self.index = 0

    def search_with_diagnostics(
        self, keyword: str, limit: int = 5
    ) -> ScraperSearchResult:
        if self.index < len(self.results):
            result = self.results[self.index]
            self.index += 1
            return result
        return ScraperSearchResult(
            store_name=self.store.name,
            store_key=self.store.key,
            keyword=keyword,
            url=self.store.search_url.format(query=keyword),
            status_code=200,
            offers=[],
            elapsed_seconds=0.01,
            source="http",
            card_count=0,
        )


if __name__ == "__main__":
    unittest.main()
