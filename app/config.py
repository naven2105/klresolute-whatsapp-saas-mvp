from __future__ import annotations

"""
File: app/config.py
Application configuration
Environment-driven (Render compatible)

Also contains:
- Client profiles (LOCKED)
  Clients are configuration, not handler forks.
"""

import os

# -------------------------------------------------------------------
# Environment configuration (EXISTING - DO NOT BREAK)
# -------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


# -------------------------------------------------------------------
# Client profiles (NEW - LOCKED)
# -------------------------------------------------------------------

class ClientProfile:
    def __init__(
        self,
        *,
        code: str,
        staff_table: str,
        inspections_enabled: bool,
        inspections_staff_only: bool,
        orders_enabled: bool,
        store_inspection_pdf: bool,
        divert_pdf_to_admin_only: bool,
    ) -> None:
        self.code = code
        self.staff_table = staff_table
        self.inspections_enabled = inspections_enabled
        self.inspections_staff_only = inspections_staff_only
        self.orders_enabled = orders_enabled
        self.store_inspection_pdf = store_inspection_pdf
        self.divert_pdf_to_admin_only = divert_pdf_to_admin_only


CLIENT_PROFILES: dict[str, ClientProfile] = {
    "MAGEN": ClientProfile(
        code="MAGEN",
        staff_table="magen_staff",
        inspections_enabled=True,
        inspections_staff_only=True,
        orders_enabled=False,
        store_inspection_pdf=True,          # Amazon S3 (Magen only)
        divert_pdf_to_admin_only=False,
    ),
    "GALITOS": ClientProfile(
        code="GALITOS",
        staff_table="galitos_staff",
        inspections_enabled=True,
        inspections_staff_only=True,
        orders_enabled=True,
        store_inspection_pdf=False,         # DO NOT store (Galitos)
        divert_pdf_to_admin_only=True,      # Divert to Admin only
    ),
}


def get_client_profile(client_code: str) -> ClientProfile | None:
    """
    Safe lookup for a client profile.
    Returns None if unknown client_code.
    """
    return CLIENT_PROFILES.get((client_code or "").upper())
