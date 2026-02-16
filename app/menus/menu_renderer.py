from __future__ import annotations

"""
File: app/menus/menu_renderer.py
Path: app/menus/menu_renderer.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Render menu JSON (from DB) into WhatsApp-safe plain text.

Rules (LOCKED):
- No DB access here.
- Emojis are allowed here (code), but must not be stored in DB.
- Must validate menu shape and fail loudly if malformed.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger("menus.menu_renderer")

# Keyword → emoji mapping (code only)
_CMD_EMOJI = {
    "ORDER": "🍔",
    "ANNOUNCEMENTS": "📣",
    "ABOUT": "ℹ️",
    "FEEDBACK": "💬",
    "STOP": "❌",
}


def _validate_menu_shape(menu: Dict[str, Any]) -> None:
    if not isinstance(menu, dict):
        raise ValueError("menu must be a dict")

    title = menu.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("menu.title must be a non-empty string")

    sections = menu.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("menu.sections must be a non-empty list")

    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            raise ValueError(f"menu.sections[{i}] must be a dict")

        sec_title = sec.get("title")
        if not isinstance(sec_title, str) or not sec_title.strip():
            raise ValueError(f"menu.sections[{i}].title must be a non-empty string")

        commands = sec.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"menu.sections[{i}].commands must be a non-empty list")


def _decorate_title(title: str) -> str:
    stripped = title.strip()
    if stripped and stripped[0] in {"📋", "🧾", "📌", "📣", "✅", "⭐", "🔥", "ℹ", "❌"}:
        return stripped
    return f"📋 {stripped}"


def _format_command(cmd: str) -> str:
    cmd_clean = cmd.strip().strip('"').strip()
    key = cmd_clean.upper()
    emoji = _CMD_EMOJI.get(key, "")
    if emoji:
        return f"{emoji} {key}"
    return key


def render_menu_text(menu_json: Dict[str, Any]) -> str:
    try:
        _validate_menu_shape(menu_json)
    except Exception:
        logger.exception("MENU_RENDER_INVALID_JSON")
        raise

    title = _decorate_title(str(menu_json["title"]))
    sections: List[Dict[str, Any]] = menu_json.get("sections", [])

    lines: List[str] = [title, ""]

    for sec in sections:
        sec_title = str(sec.get("title", "")).strip()
        lines.append(sec_title)
        commands = sec.get("commands") or []
        for c in commands:
            if isinstance(c, str) and c.strip():
                lines.append(_format_command(c))
        lines.append("")

    return "\n".join(lines).strip()
