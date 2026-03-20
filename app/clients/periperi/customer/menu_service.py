# ==================================================
# File: menu_service.py
# Path: app/clients/periperi/customer/menu_service.py
# Project: KLResolute WhatsApp SaaS MVP
#
# Patch:
# - Full flavour map
# - DB-driven smart matching (no keyword dependency)
# ==================================================

from __future__ import annotations

import random
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.messaging.client_messenger import send_message

logger = logging.getLogger("periperi.menu_service")


# --------------------------------------------------
# FLAVOUR MAP
# --------------------------------------------------

FLAVOUR_MAP = {

    "12 Prawns": [
        "juicy flame-grilled prawns with bold peri-peri 🔥",
        "succulent prawns grilled to perfection",
        "fresh prawns bursting with Portuguese flavour 🇵🇹",
        "tender, juicy and full of ocean flavour",
        "rich, buttery prawns with a spicy kick",
        "perfectly charred and incredibly juicy",
        "light, zesty and mouth-wateringly good",
        "grilled prawns with our signature peri-peri heat",
        "a seafood favourite done right",
        "simple, fresh and unforgettable",
    ],
    "Prawns & Calamari": [
        "fresh calamari and juicy prawns in perfect harmony 🦑",
        "the ultimate seafood combo, grilled to perfection",
        "tender calamari with flavour-packed prawns",
        "light, fresh and full of ocean goodness",
        "rich garlic, lemon and peri-peri flavours",
        "a perfect balance of texture and taste",
        "seafood lovers’ favourite combo",
        "crispy, tender and bursting with flavour",
        "grilled the Portuguese way 🇵🇹",
        "fresh, vibrant and satisfying",
    ],
    "Chicken & Prawns": [
        "tender chicken and juicy prawns with a spicy twist 🐔",
        "the perfect land & sea combo",
        "flame-grilled chicken paired with succulent prawns",
        "bold peri-peri flavour in every bite",
        "rich, savoury and slightly spicy",
        "a hearty and satisfying favourite",
        "Portuguese-style grilled perfection 🇵🇹",
        "comfort food with a seafood twist",
        "juicy chicken balanced with fresh prawns",
        "flavour-packed and filling",
    ],
    "Half Chicken": [
        "flame-grilled and full of peri-peri flavour 🐔",
        "juicy, tender and perfectly spiced",
        "a true Portuguese classic 🇵🇹",
        "grilled to perfection with bold flavour",
        "simple, hearty and satisfying",
        "rich, smoky and delicious",
        "crispy outside, juicy inside",
        "your go-to comfort meal",
        "packed with flavour in every bite",
        "a customer favourite every time",
    ],
    "Quarter Chicken": [
        "perfectly grilled and full of flavour 🐔",
        "light, juicy and satisfying",
        "great for a quick, tasty meal",
        "flame-grilled with peri-peri spice",
        "simple and delicious every time",
        "tender chicken done right",
        "a small meal with big flavour",
        "fresh off the grill",
        "quick, tasty and satisfying",
        "perfectly portioned goodness",
    ],
    "Chicken Livers": [
        "rich, saucy and full of flavour 🔥",
        "tender livers in a creamy garlic sauce",
        "a bold Portuguese favourite 🇵🇹",
        "spicy, savoury and satisfying",
        "perfect with a fresh roll",
        "deep, rich and comforting",
        "a classic starter done right",
        "flavour-packed and hearty",
        "creamy, spicy and delicious",
        "a must-try for liver lovers",
    ],
    "Rump Steak": [
        "juicy, tender and grilled to perfection 🥩",
        "a classic cut packed with flavour",
        "seasoned and flame-grilled just right",
        "rich, hearty and satisfying",
        "perfect for steak lovers",
        "simple, bold and delicious",
        "grilled with Portuguese flair 🇵🇹",
        "tender and full of flavour",
        "a premium grilled favourite",
        "perfectly cooked every time",
    ],
    "Pork Ribs 300g": [
        "sticky, tender and full of BBQ flavour 🔥",
        "fall-off-the-bone delicious",
        "rich, smoky and satisfying",
        "perfectly grilled and basted",
        "a rib lover’s dream",
        "bold, juicy and flavour-packed",
        "slow-cooked and flame-finished",
        "messy, tasty and worth it",
        "sweet, smoky and irresistible",
        "grilled to perfection",
    ],
    "Chicken Burger": [
        "juicy grilled chicken on a fresh roll 🍔",
        "simple, tasty and satisfying",
        "perfectly grilled with fresh toppings",
        "a classic done right",
        "light, fresh and full of flavour",
        "your everyday favourite",
        "grilled chicken goodness",
        "quick, tasty and filling",
        "a go-to comfort meal",
        "flavourful and satisfying",
    ],
    "Beef Prego Roll": [
        "tender beef in our famous prego sauce 🔥",
        "a Portuguese street food favourite 🇵🇹",
        "juicy, saucy and full of flavour",
        "perfectly grilled and served fresh",
        "rich, bold and satisfying",
        "a classic prego experience",
        "simple, hearty and delicious",
        "packed with flavour in every bite",
        "fresh off the grill",
        "a must-try favourite",
    ],
}


# --------------------------------------------------
# FETCH MENU
# --------------------------------------------------

def get_menu_items_by_category(db: Session, category: str):
    return db.execute(
        text(
            """
            SELECT name, price
            FROM r_periperi__menu_items
            WHERE LOWER(category) = LOWER(:category)
              AND active = TRUE
            ORDER BY name
            """
        ),
        {"category": category},
    ).fetchall()


# --------------------------------------------------
# BUILD RESPONSE
# --------------------------------------------------

def build_menu_response(items):

    lines = []

    for i in items:
        flavours = FLAVOUR_MAP.get(i.name)
        flavour_text = random.choice(flavours) if flavours else None

        if flavour_text:
            lines.append(f"• {i.name} — {flavour_text} (R{i.price})")
        else:
            lines.append(f"• {i.name} (R{i.price})")

    return "\n".join(lines)


# --------------------------------------------------
# HANDLE MENU COMMAND (SMART MATCH)
# --------------------------------------------------

def handle_menu_command(
    *,
    db: Session,
    sender_msisdn: str,
    business_msisdn: str,
    message_text: str,
) -> bool:

    msg = message_text.lower()

    # --------------------------------------------------
    # LOAD ALL ITEMS
    # --------------------------------------------------

    all_items = db.execute(
        text(
            """
            SELECT name, category
            FROM r_periperi__menu_items
            WHERE active = TRUE
            """
        )
    ).fetchall()

    matched_category = None

    for item in all_items:
        name_lower = item.name.lower()

        if any(word in msg for word in name_lower.split()):
            matched_category = item.category
            break

    # --------------------------------------------------
    # RESPONSE
    # --------------------------------------------------

    if matched_category:

        items = get_menu_items_by_category(db, matched_category)

        if not items:
            return True

        response = (
            "🔥 Great choice!\n\n"
            f"Here are some {matched_category.lower()} favourites:\n\n"
            f"{build_menu_response(items)}\n\n"
            "All with a Portuguese twist 🇵🇹\n\n"
            "Type menu to explore more or specials for deals"
        )

        send_message(
            db=db,
            business_msisdn=business_msisdn,
            to_number=sender_msisdn,
            text=response,
        )

        return True

    return False