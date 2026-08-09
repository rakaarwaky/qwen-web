from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


PaymentStatus = Literal["pending", "authorized", "captured", "failed", "refunded"]


@dataclass(frozen=True)
class PaymentResult:
    id: str
    status: PaymentStatus
    amount_cents: int
    currency: str
    provider: Literal["card", "gopay", "ovo"]
    created_at: str


class PaymentFeature:
    """Payment processing: credit card + digital wallet."""

    def __init__(self, clock: datetime | None = None) -> None:
        self._now = clock or datetime.utcnow

    def pay_with_card(
        self, card_token: str, amount_cents: int, currency: str = "USD"
    ) -> PaymentResult:
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        if not card_token:
            raise ValueError("card_token is required")
        return self._charge("card", amount_cents, currency)

    def pay_with_wallet(
        self, wallet: Literal["gopay", "ovo"], amount_cents: int, currency: str = "IDR"
    ) -> PaymentResult:
        if wallet not in ("gopay", "ovo"):
            raise ValueError("unsupported wallet")
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        return self._charge(wallet, amount_cents, currency)

    def refund(
        self, payment_id: str, amount_cents: int | None = None
    ) -> PaymentResult:
        if amount_cents is not None and amount_cents <= 0:
            raise ValueError("refund amount must be positive")
        return PaymentResult(
            id=f"{payment_id}-refund",
            status="refunded",
            amount_cents=amount_cents or 0,
            currency="USD",
            provider="card",
            created_at=self._now().isoformat(),
        )

    def _charge(
        self, provider: str, amount_cents: int, currency: str
    ) -> PaymentResult:
        return PaymentResult(
            id=f"{provider}-{amount_cents}-{int(self._now().timestamp())}",
            status="captured",
            amount_cents=amount_cents,
            currency=currency,
            provider=provider,  # type: ignore[arg-type]
            created_at=self._now().isoformat(),
        )
