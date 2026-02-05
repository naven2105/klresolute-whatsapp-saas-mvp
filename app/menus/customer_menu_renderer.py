from __future__ import annotations

"""
File: app/menus/customer_menu_renderer.py
Path: app/menus/customer_menu_renderer.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Render DB-stored customer menu JSON into WhatsApp-safe text.

Rules (LOCKED):
- Pure renderer (no DB access)
- No outbound messaging
- Deterministic output
- Emojis allowed
"""

import logging
from typing import Any

logger = logging.getLogger("menus.customer_menu_renderer")


def render_menu_text(menu_json: dict[str, Any]) -> str:
    """
    Convert menu_json to plain text.

    Expected shape:
    {
      "title": str,
      "sections": [
        {
          "title": str,
          "commands": [str, ...]
        }
      ]
    }
    """
    if not isinstance(menu_json, dict):
        logger.error(
            "MENU_RENDER_INVALID_INPUT | type=%s | value=%r",
            type(menu_json).__name__,
            menu_json,
        )
        return "Menu unavailable."

    lines: list[str] = []

    title = menu_json.get("title")
    if title:
        lines.append(str(title))
        lines.append("")
    else:
        logger.warning("MENU_RENDER_MISSING_TITLE")

    sections = menu_json.get("sections")
    if not isinstance(sections, list):
        logger.error("MENU_RENDER_INVALID_SECTIONS | sections=%r", sections)
        return "\n".join(lines).strip() or "Menu unavailable."

    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            logger.warning(
                "MENU_RENDER_INVALID_SECTION | index=%s | value=%r",
                idx,
                section,
            )
            continue

        section_title = section.get("title")
        if section_title:
            lines.append(str(section_title))

        commands = section.get("commands", [])
        if not isinstance(commands, list):
            logger.warning(
                "MENU_RENDER_INVALID_COMMANDS | index=%s | value=%r",
                idx,
                commands,
            )
            continue

        for cmd in commands:
            lines.append(str(cmd))

        lines.append("")

    output = "\n".join(lines).strip()
    if not output:
        logger.error("MENU_RENDER_EMPTY_OUTPUT | menu_json=%r", menu_json)
        return "Menu unavailable."

    logger.info("MENU_RENDER_SUCCESS | sections=%s", len(sections))
    return output
