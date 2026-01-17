"""
File: app/services/order_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Persist confirmed single-item orders (Phase 1).

Design rules:
- Write-only service
- No WhatsApp logic
- No menu logic
- No validation beyond basic assertions
- Caller must provide final calculated values
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session
from sqlalchemy import text


DrinkAddon = Literal["NONE", "300ML", "1_5L"]
Flavour = Literal["L", "M", "H"]


@dataclass(frozen=True)
class OrderCreate:
    client_id: str
    customer_msisdn: str

    item_sku: str
    item_name: str
    flavour: Flavour

    base_price: int
    drink_addon: DrinkAddon
    addon_price: int

    total_amount: int
    confirmed_at: datetime


def create_order(db: Session, order: OrderCreate) -> None:
    """
    Insert a confirmed order into the database.

    Assumptions:
    - Order is already confirmed (YES received)
    - Prices and totals are already calculated
    - Caller guarantees correctness
    """

    sql = text(
        """
        INSERT INTO orders (
            client_id,
            customer_msisdn,
            item_sku,
            item_name,
            flavour,
            base_price,
            drink_addon,
            addon_price,
            total_amount,
            confirmed_at,
            status
        )
        VALUES (
            :client_id,
            :customer_msisdn,
            :item_sku,
            :item_name,
            :flavour,
            :base_price,
            :drink_addon,
            :addon_price,
            :total_amount,
            :confirmed_at,
            'CONFIRMED'
        )
        """
    )

    db.execute(
        sql,
        {
            "client_id": order.client_id,
            "customer_msisdn": order.customer_msisdn,
            "item_sku": order.item_sku,
            "item_name": order.item_name,
            "flavour": order.flavour,
            "base_price": order.base_price,
            "drink_addon": order.drink_addon,
            "addon_price": order.addon_price,
            "total_amount": order.total_amount,
            "confirmed_at": order.confirmed_at,
        },
    )

    db.commit()
