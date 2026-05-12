from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from src.config.stores import StoreConfig
from src.database.connection import Database
from src.scrapers.base import ProductOffer


class RadarRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_store(self, store: StoreConfig) -> int:
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO stores (name, base_url, trust_score, marketplace_risk)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    base_url = excluded.base_url,
                    trust_score = excluded.trust_score,
                    marketplace_risk = excluded.marketplace_risk
                """,
                (store.name, store.base_url, store.trust_score, store.marketplace_risk),
            )
            row = connection.execute(
                "SELECT id FROM stores WHERE name = ?", (store.name,)
            ).fetchone()
            connection.commit()
            return int(row["id"])

    def upsert_product(self, offer: ProductOffer, store_id: int) -> int:
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO products (name, category, store_id, url)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(store_id, url) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (offer.name, offer.category, store_id, offer.url),
            )
            row = connection.execute(
                "SELECT id FROM products WHERE store_id = ? AND url = ?",
                (store_id, offer.url),
            ).fetchone()
            connection.commit()
            return int(row["id"])

    def insert_price_history(self, product_id: int, offer: ProductOffer) -> None:
        payload = {
            "keyword": offer.keyword,
            "source": offer.source,
            "listed_original_price": offer.listed_original_price,
            "marketplace_name": offer.marketplace_name,
            "shipping_price": offer.shipping_price,
            "tax_price": offer.tax_price,
        }
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO price_history (product_id, price, source_payload)
                VALUES (?, ?, ?)
                """,
                (product_id, offer.current_price, json.dumps(payload, ensure_ascii=True)),
            )
            connection.commit()

    def average_price_before_current(self, product_id: int, limit: int = 20) -> float | None:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT price FROM price_history
                WHERE product_id = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
                """,
                (product_id, limit),
            ).fetchall()
        prices = [float(row["price"]) for row in rows]
        if len(prices) < 2:
            return None
        return sum(prices[1:]) / len(prices[1:])

    def insert_deal(
        self,
        product_id: int,
        current_price: float,
        estimated_avg_price: float,
        discount_percent: float,
        score: int,
        alert_reason: str,
        verdict: str,
    ) -> int:
        with self.db.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO deals (
                    product_id, current_price, estimated_avg_price,
                    discount_percent, score, alert_reason, verdict
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    current_price,
                    estimated_avg_price,
                    discount_percent,
                    score,
                    alert_reason,
                    verdict,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def mark_deal_notified(self, deal_id: int) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE deals SET notified_at = CURRENT_TIMESTAMP WHERE id = ?",
                (deal_id,),
            )
            connection.commit()

    def has_recent_similar_deal(
        self, product_id: int, current_price: float, hours: int = 12
    ) -> bool:
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT id FROM deals
                WHERE product_id = ?
                  AND ABS(current_price - ?) < 0.01
                  AND detected_at >= ?
                LIMIT 1
                """,
                (product_id, current_price, since),
            ).fetchone()
        return row is not None

    def latest_deals(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.*,
                    p.name AS product_name,
                    p.category,
                    p.url,
                    s.name AS store_name
                FROM deals d
                JOIN products p ON p.id = d.product_id
                JOIN stores s ON s.id = p.store_id
                ORDER BY d.detected_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

