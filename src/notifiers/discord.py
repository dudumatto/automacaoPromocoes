from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from src.config.settings import Settings
from src.scrapers.base import ProductOffer


ALERT_EMOJI = "\U0001F6A8"
ABSURD_THRESHOLD_SCORE = 90
ABSURD_THRESHOLD_DISCOUNT = 40.0

HARDWARE_CATEGORIES = {
    "placa de video",
    "gpu",
    "processador",
    "cpu",
    "memoria ram",
    "ram",
    "ssd",
    "nvme",
    "fonte",
    "placa mae",
}

SETUP_CATEGORIES = {
    "setup",
    "monitor",
    "braco articulado",
    "braco articulado de monitor",
    "light bar",
    "teclado",
    "mouse",
    "mousepad",
    "headset",
    "suporte headset",
    "suporte de headset",
    "decoracao",
    "decoracao de setup",
    "led",
    "acessorio",
    "organizador",
    "organizadores de mesa",
    "acessorios",
}


def money(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


@dataclass(frozen=True)
class DealAlert:
    offer: ProductOffer
    estimated_average_price: float
    discount_percent: float
    score: int
    verdict: str
    reason: str


@dataclass(frozen=True)
class DiscordChannel:
    key: str
    env_name: str
    webhook_url: str


class DiscordNotifier:
    def __init__(
        self,
        webhook_url: str = "",
        *,
        hardware_webhook_url: str = "",
        setup_webhook_url: str = "",
        absurdas_webhook_url: str = "",
    ) -> None:
        self.fallback_webhook_url = webhook_url.strip()
        self.hardware_webhook_url = hardware_webhook_url.strip()
        self.setup_webhook_url = setup_webhook_url.strip()
        self.absurdas_webhook_url = absurdas_webhook_url.strip()
        self._sent_signatures: set[tuple[str, str]] = set()

    @classmethod
    def from_settings(cls, settings: Settings) -> "DiscordNotifier":
        return cls(
            settings.discord_webhook_url,
            hardware_webhook_url=settings.discord_webhook_hardware,
            setup_webhook_url=settings.discord_webhook_setup,
            absurdas_webhook_url=settings.discord_webhook_absurdas,
        )

    def send_deal_alert(
        self,
        deal: DealAlert | None = None,
        *,
        offer: ProductOffer | None = None,
        estimated_average_price: float | None = None,
        discount_percent: float | None = None,
        score: int | None = None,
        verdict: str | None = None,
        reason: str | None = None,
    ) -> bool:
        deal = deal or self._deal_from_legacy_args(
            offer=offer,
            estimated_average_price=estimated_average_price,
            discount_percent=discount_percent,
            score=score,
            verdict=verdict,
            reason=reason,
        )
        channels = self.resolve_channels(deal)
        if not channels:
            print("Aviso: nenhum webhook Discord configurado para esta promocao.")
            return False

        payload = self.build_payload(deal)
        sent_any = False
        signature = self.deal_signature(deal)
        for channel in channels:
            if not channel.webhook_url:
                continue
            channel_key = (channel.key, signature)
            if channel_key in self._sent_signatures:
                print(
                    "Aviso: envio duplicado ignorado para "
                    f"{channel.env_name} ({deal.offer.name[:80]})."
                )
                continue
            try:
                response = requests.post(channel.webhook_url, json=payload, timeout=15)
                response.raise_for_status()
                self._sent_signatures.add(channel_key)
                sent_any = True
            except requests.RequestException as exc:
                print(f"Falha ao enviar alerta Discord para {channel.env_name}: {exc}")
        return sent_any

    def resolve_channels(self, deal: DealAlert) -> list[DiscordChannel]:
        selected: list[DiscordChannel] = []
        if (
            deal.score >= ABSURD_THRESHOLD_SCORE
            or deal.discount_percent >= ABSURD_THRESHOLD_DISCOUNT
        ):
            selected.append(
                self._channel(
                    key="promos-absurdas",
                    env_name="DISCORD_WEBHOOK_ABSURDAS",
                    webhook_url=self.absurdas_webhook_url,
                )
            )

        category = normalize_text(deal.offer.category)
        if matches_category(category, HARDWARE_CATEGORIES):
            selected.append(
                self._channel(
                    key="promos-hardware",
                    env_name="DISCORD_WEBHOOK_HARDWARE",
                    webhook_url=self.hardware_webhook_url,
                )
            )
        if matches_category(category, SETUP_CATEGORIES):
            selected.append(
                self._channel(
                    key="promos-setup",
                    env_name="DISCORD_WEBHOOK_SETUP",
                    webhook_url=self.setup_webhook_url,
                )
            )

        if not selected and self.fallback_webhook_url:
            selected.append(
                DiscordChannel(
                    key="discord-fallback",
                    env_name="DISCORD_WEBHOOK_URL",
                    webhook_url=self.fallback_webhook_url,
                )
            )

        unique_channels: list[DiscordChannel] = []
        seen_keys: set[str] = set()
        for channel in selected:
            if channel.key in seen_keys:
                continue
            seen_keys.add(channel.key)
            unique_channels.append(channel)
        return unique_channels

    def build_payload(self, deal: DealAlert) -> dict:
        offer = deal.offer
        savings = deal.estimated_average_price - offer.current_price
        return {
            "username": "Radar Setup",
            "embeds": [
                {
                    "title": f"{ALERT_EMOJI} {deal.verdict}: {offer.name[:180]}",
                    "url": offer.url,
                    "color": self.color_for_score(deal.score),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "description": (
                        f"Oferta em **{offer.store}** com queda de "
                        f"**{deal.discount_percent:.1f}%**."
                    ),
                    "fields": [
                        {"name": "Produto", "value": offer.name[:1024], "inline": False},
                        {
                            "name": "Preco atual",
                            "value": money(offer.current_price),
                            "inline": True,
                        },
                        {
                            "name": "Media estimada",
                            "value": money(deal.estimated_average_price),
                            "inline": True,
                        },
                        {
                            "name": "Economia estimada",
                            "value": money(max(0.0, savings)),
                            "inline": True,
                        },
                        {
                            "name": "Queda",
                            "value": f"{deal.discount_percent:.1f}%",
                            "inline": True,
                        },
                        {"name": "Loja", "value": offer.store, "inline": True},
                        {"name": "Categoria", "value": offer.category, "inline": True},
                        {"name": "Score", "value": f"{deal.score}/100", "inline": True},
                        {"name": "Veredito", "value": deal.verdict, "inline": True},
                        {"name": "Motivo", "value": deal.reason[:1024], "inline": False},
                        {"name": "Link", "value": offer.url[:1024], "inline": False},
                    ],
                    "footer": {"text": "Radar Setup - alerta local"},
                }
            ],
        }

    def _channel(self, key: str, env_name: str, webhook_url: str) -> DiscordChannel:
        if webhook_url:
            return DiscordChannel(key=key, env_name=env_name, webhook_url=webhook_url)
        if self.fallback_webhook_url:
            print(
                f"Aviso: {env_name} vazio; usando DISCORD_WEBHOOK_URL como fallback."
            )
            return DiscordChannel(
                key=key,
                env_name=f"{env_name} via DISCORD_WEBHOOK_URL",
                webhook_url=self.fallback_webhook_url,
            )
        print(f"Aviso: {env_name} vazio; alerta nao enviado para {key}.")
        return DiscordChannel(key=key, env_name=env_name, webhook_url="")

    def _deal_from_legacy_args(
        self,
        *,
        offer: ProductOffer | None,
        estimated_average_price: float | None,
        discount_percent: float | None,
        score: int | None,
        verdict: str | None,
        reason: str | None,
    ) -> DealAlert:
        if (
            offer is None
            or estimated_average_price is None
            or discount_percent is None
            or score is None
            or verdict is None
            or reason is None
        ):
            raise ValueError("Informe um DealAlert ou todos os campos do alerta.")
        return DealAlert(
            offer=offer,
            estimated_average_price=estimated_average_price,
            discount_percent=discount_percent,
            score=score,
            verdict=verdict,
            reason=reason,
        )

    @staticmethod
    def deal_signature(deal: DealAlert) -> str:
        raw = "|".join(
            [
                deal.offer.url.strip().lower().split("?")[0],
                deal.offer.name.strip().lower(),
                f"{deal.offer.current_price:.2f}",
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def color_for_score(score: int) -> int:
        if score >= 90:
            return 0xE11D48
        if score >= 80:
            return 0xF59E0B
        return 0x2563EB


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower().strip())
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_accents.split())


def matches_category(category: str, candidates: set[str]) -> bool:
    normalized_candidates = {normalize_text(candidate) for candidate in candidates}
    return any(
        category == candidate
        or category.startswith(f"{candidate} ")
        or candidate in category
        for candidate in normalized_candidates
    )
