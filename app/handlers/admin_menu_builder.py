from __future__ import annotations

"""
File: app/admin/menu_builder.py
Path: app/admin/menu_builder.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
DB-backed Admin Menu builder (multi-client).

Rules (LOCKED):
- Read-only DB access
- Client identity uses INTEGER client_id ONLY
- No UUID client resolution here
- No WhatsApp sending here
- Fail closed: return a safe default menu if DB menu missing
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("admin.menu_builder")


# -------------------------------------------------
# Default (safe fallback) — used only if DB menu is missing
# -------------------------------------------------
_DEFAULT_ADMIN_MENU_TEXT = (
    "🛠️ Admin Menu\n\n"
    "📊 Surveys\n"
    "SENTIMENT → 👍 😐 👎\n"
    "FREQUENCY → DAILY | WEEKLY | MONTHLY\n"
    "HELPFULNESS → YES | NO\n"
    "END SURVEY\n\n"
    "ℹ️ Survey notes:\n"
    "• Surveys automatically close after 24 hours\n"
    "• Starting a new survey within 24 hours will close the previous one\n"
    "• Survey results are shared with admins automatically\n\n"
    "🔥 Specials\n"
    "SPECIALS IMAGE → <send image + caption>\n"
    "CLEAR SPECIALS\n\n"
    "ℹ️ Specials notes:\n"
    "• Only one special can be active at a time\n"
    "• Customers can only access the latest special\n\n"
    "✉️ Messaging\n"
    "SEND: <number> <message>\n\n"
    "ℹ️ Messaging notes:\n"
    "• Messages are sent to one customer at a time\n\n"
    "⚙️ System\n"
    "STATUS: <message>\n"
    "CLEAR STATUS"
)


def get_admin_menu_text(
    *,
    db: Session,
    client_id: int,
    menu_key: str = "admin_menu",
) -> str:
    """
    Fetch admin menu text for a client (INTEGER client_id).
    Returns DB menu if present, else returns safe default.
    Never raises.
    """

    # Guard rails
    if not isinstance(client_id, int):
        try:
            client_id = int(str(client_id))
        except Exception:
            logger.error("ADMIN_MENU_CLIENT_ID_INVALID | client_id=%r", client_id)
            return _DEFAULT_ADMIN_MENU_TEXT

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT menu_text
                    FROM client_admin_menus
                    WHERE client_id = :client_id
                      AND menu_key = :menu_key
                      AND is_active = TRUE
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "menu_key": menu_key},
            )
            .mappings()
            .first()
        )

        if not row or not (row.get("menu_text") or "").strip():
            logger.warning(
                "ADMIN_MENU_NOT_FOUND | client_id=%s | menu_key=%s | using_default=1",
                client_id,
                menu_key,
            )
            return _DEFAULT_ADMIN_MENU_TEXT

        logger.info(
            "ADMIN_MENU_LOADED | client_id=%s | menu_key=%s | using_default=0",
            client_id,
            menu_key,
        )
        return str(row["menu_text"]).strip()

    except Exception:
        logger.exception(
            "ADMIN_MENU_LOAD_FAIL | client_id=%s | menu_key=%s | using_default=1",
            client_id,
            menu_key,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return _DEFAULT_ADMIN_MENU_TEXT
