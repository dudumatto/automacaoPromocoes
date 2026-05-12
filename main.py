from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from src.config.settings import Settings
from src.database.connection import Database
from src.database.schema import initialize_database
from src.notifiers.discord import DiscordNotifier
from src.scrapers.base import ScraperErrorKind
from src.scrapers.registry import build_scraper, store_by_key_or_name
from src.services.scanner import DealScanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Radar Setup",
        description="Monitora promocoes de hardware e itens de setup.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan", help="Executa uma varredura nas lojas configuradas.")
    subparsers.add_parser("test-alert", help="Envia ou exibe um alerta de teste.")
    debug_parser = subparsers.add_parser(
        "debug-store",
        help="Testa uma loja e keyword, salvando HTML parcial em data/debug/.",
    )
    debug_parser.add_argument("--store", required=True, help="Chave ou nome da loja.")
    debug_parser.add_argument("--keyword", required=True, help="Keyword pesquisada.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = Settings.from_env()
    db = Database(settings.database_path)
    initialize_database(db)

    notifier = DiscordNotifier.from_settings(settings)
    scanner = DealScanner(db=db, settings=settings, notifier=notifier)

    if args.command == "scan":
        summary = scanner.scan()
        print_scan_summary(summary)
        return 0

    if args.command == "test-alert":
        scanner.send_test_alert()
        return 0

    if args.command == "debug-store":
        return debug_store(args.store, args.keyword, settings)

    return 1


def print_scan_summary(summary: object) -> None:
    print("Scan finalizado:")
    print(f"- produtos vistos: {summary.products_seen}")
    print(f"- ofertas registradas: {summary.deals_found}")
    print(f"- alertas enviados: {summary.alerts_sent}")
    print(f"- lojas OK: {format_store_list(summary.ok_stores)}")
    print(
        "- lojas bloqueadas: "
        f"{format_store_counts(summary.stores_by_error_kind(ScraperErrorKind.BLOCKED))}"
    )
    print(
        "- lojas indisponiveis: "
        f"{format_store_counts(summary.stores_by_error_kind(ScraperErrorKind.TEMPORARY_UNAVAILABLE))}"
    )
    other_errors = {}
    for store, counts in summary.error_counts_by_store.items():
        count = sum(
            value
            for key, value in counts.items()
            if key
            not in {
                ScraperErrorKind.BLOCKED.value,
                ScraperErrorKind.TEMPORARY_UNAVAILABLE.value,
            }
        )
        if count:
            other_errors[store] = count
    print(f"- outros erros: {format_store_counts(other_errors)}")
    print(f"- tempo total: {summary.elapsed_seconds:.0f}s")


def format_store_list(stores: list[str]) -> str:
    return ", ".join(stores) if stores else "nenhuma"


def format_store_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "nenhuma"
    return ", ".join(f"{store} {count}x" for store, count in counts.items())


def debug_store(store_value: str, keyword: str, settings: Settings) -> int:
    store = store_by_key_or_name(store_value)
    scraper = build_scraper(
        store=store,
        timeout_seconds=settings.request_timeout_seconds,
        enable_playwright_fallback=settings.enable_playwright_fallback,
        max_retries=settings.max_retries,
    )
    result = scraper.search_with_diagnostics(
        keyword=keyword,
        limit=settings.max_results_per_store,
        include_html=True,
    )
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9_-]+", "_", f"{store.key}_{keyword}".lower()).strip("_")
    debug_path = debug_dir / f"{slug}.html"
    partial_html = result.html[:200_000] if result.html else ""
    debug_path.write_text(partial_html, encoding="utf-8")

    print("Debug store:")
    print(f"- loja: {store.name}")
    print(f"- keyword: {keyword}")
    print(f"- URL: {result.url}")
    print(f"- status HTTP: {result.status_code if result.status_code else 'sem-status'}")
    print(f"- fonte: {result.source}")
    print(f"- HTML parcial salvo em: {debug_path}")
    print(f"- cards encontrados: {result.card_count}")
    print(f"- produtos parseados: {len(result.offers)}")
    print("- seletores usados:")
    for key, value in scraper.selector_report().items():
        print(f"  - {key}: {value or '(nao usado)'}")
    if result.error_kind:
        print(f"- erro: {result.error_kind.value}")
        print(f"- motivo: {result.error_message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
