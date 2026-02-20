from __future__ import annotations

"""
File: tenant_validator.py
Path: app/platform/tenant_validator.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Strict validation for tenant table_prefix.

Architecture Rules:
- Must start with 'r_'
- Lowercase only
- Alphanumeric + underscore only
- No spaces
- No hyphens
- Cannot end with underscore
- No double underscore allowed
- Immutable after creation (enforced elsewhere)

This validator is mandatory before inserting into restaurants table.
Hard-fail on violation.
"""

import re
import logging

logger = logging.getLogger("platform.tenant_validator")

PREFIX_PATTERN = re.compile(r"^r_[a-z0-9_]+$")


def validate_table_prefix(prefix: str) -> None:
    """
    Validate tenant table_prefix.

    Raises:
        ValueError: if validation fails.
    """

    logger.info("TENANT_PREFIX_VALIDATE_START | prefix=%s", prefix)

    if prefix is None:
        logger.error("TENANT_PREFIX_INVALID | reason=null_prefix")
        raise ValueError("table_prefix cannot be None")

    prefix = prefix.strip()

    if not prefix:
        logger.error("TENANT_PREFIX_INVALID | reason=empty_prefix")
        raise ValueError("table_prefix cannot be empty")

    if len(prefix) < 4:
        logger.error("TENANT_PREFIX_INVALID | reason=too_short | prefix=%s", prefix)
        raise ValueError("table_prefix too short")

    if len(prefix) > 40:
        logger.error("TENANT_PREFIX_INVALID | reason=too_long | prefix=%s", prefix)
        raise ValueError("table_prefix too long")

    if not PREFIX_PATTERN.fullmatch(prefix):
        logger.error(
            "TENANT_PREFIX_INVALID | reason=regex_fail | prefix=%s",
            prefix,
        )
        raise ValueError(
            "Invalid table_prefix. Must match pattern: r_[a-z0-9_]+"
        )

    if prefix.endswith("_"):
        logger.error(
            "TENANT_PREFIX_INVALID | reason=trailing_underscore | prefix=%s",
            prefix,
        )
        raise ValueError("table_prefix cannot end with underscore")

    if "__" in prefix:
        logger.error(
            "TENANT_PREFIX_INVALID | reason=double_underscore | prefix=%s",
            prefix,
        )
        raise ValueError("table_prefix cannot contain double underscore")

    logger.info("TENANT_PREFIX_VALIDATE_SUCCESS | prefix=%s", prefix)
