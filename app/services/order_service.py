from __future__ import annotations

"""
File: app/services/order_service.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Persist confirmed single-item orders (Phase 1).

Design rules:
- Write-only service
- No WhatsApp logic
- No menu logic
- Timestamp responsibility lives HERE
- South African time is stored in DB
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Literal

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("service.order")


DrinkAddon = Literal["NONE", "300ML", "1_5L"]
Flavour = Literal["L", "M", "H"]


@dataclass(frozen=True)
class OrderCreate:
    client_id: int
    customer_msisdn: str

    item_sku: str
    item_name: str
    flavour: Flavour

    base_price: int
    drink_addon: DrinkAddon
    addon_price: int

    total_amount: int


def _now_sa() -> datetime:
    """Return current South African time."""
    return datetime.now(tz=ZoneInfo("Africa/Johannesburg"))


def create_order(db: Session, order: OrderCreate) -> None:
    """
    Insert a confirmed order into the database.

    SA time is applied here.
    """

    confirmed_at = _now_sa()

    logger.info(
        "ORDER_CREATE_ENTER | client_id=%s | customer=%s | item=%s | confirmed_at=%s",
        order.client_id,
        order.customer_msisdn,
        order.item_name,
        confirmed_at,
    )

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
            "confirmed_at": confirmed_at,
        },
    )

    db.commit()

    logger.info(
        "ORDER_CREATE_SUCCESS | client_id=%s | customer=%s",
        order.client_id,
        order.customer_msisdn,
    )
