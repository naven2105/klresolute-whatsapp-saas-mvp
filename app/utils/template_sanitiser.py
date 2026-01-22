from __future__ import annotations

import logging
import re

logger = logging.getLogger("template_sanitiser")

# Meta rules:
# - no \n or \t
# - no more than 4 consecutive spaces
# - trimmed
_SPACE_RE = re.compile(r"\s{5,}")

def sanitise_template_text(text: str) -> str:
    """
    Prepare text for WhatsApp templates.
    Safe for ADMIN templates only.
    """

    if not text:
        return ""

    original = text

    # replace newlines / tabs with single space
    text = text.replace("\n", " ").replace("\t", " ")

    # collapse long whitespace
    text = _SPACE_RE.sub("    ", text)

    # trim
    text = text.strip()

    if text != original:
        logger.info(
            "TEMPLATE_TEXT_SANITISED | before=%r | after=%r",
            original,
            text,
        )

    return text
