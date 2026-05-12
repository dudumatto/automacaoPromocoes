from __future__ import annotations

import re
import unicodedata


CURRENCY_PRICE_RE = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))?")
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))")


def parse_price(value: str) -> float | None:
    normalized = value.replace("\xa0", " ").strip()
    matches = CURRENCY_PRICE_RE.findall(normalized) or PRICE_RE.findall(normalized)
    if not matches:
        return None

    parsed_prices: list[float] = []
    for whole, cents in matches:
        if len(whole) <= 2 and not cents:
            continue
        number = whole.replace(".", "")
        cents = cents or "00"
        try:
            parsed_prices.append(float(f"{number}.{cents}"))
        except ValueError:
            continue

    if not parsed_prices:
        return None
    return parsed_prices[0]


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def parse_labeled_price(value: str, labels: list[str]) -> float | None:
    normalized = value.replace("\xa0", " ")
    searchable = strip_accents(normalized).lower()
    normalized_labels = [strip_accents(label).lower() for label in labels]

    for label in normalized_labels:
        start = 0
        while True:
            index = searchable.find(label, start)
            if index == -1:
                break
            snippet = normalized[index : index + 90]
            snippet_searchable = searchable[index : index + 90]
            if "gratis" in snippet_searchable or "free" in snippet_searchable:
                return 0.0
            price = parse_price(snippet)
            if price is not None:
                return price
            start = index + len(label)
    return None
