from __future__ import annotations

"""
File: app/profiles/client_profile.py
Path: app/profiles/client_profile.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Client profile definitions and resolution.

Rules:
- Profiles define enabled modules
- Profiles define admin MSISDNs
- No business logic here
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass(frozen=True)
class ClientProfile:
    client_code: str
    business_msisdn: str
    admin_numbers: list[str]
    enabled_modules: list[str]


# -------------------------------------------------
# Admin allowlist (shared for MVP)
# -------------------------------------------------

_ADMIN_ALLOWLIST = [
    n.strip()
    for n in os.getenv("OUTBOUND_TEST_ALLOWLIST", "").split(",")
    if n.strip()
]


# -------------------------------------------------
# Client profiles (FROZEN)
# -------------------------------------------------

_PROFILES: dict[str, ClientProfile] = {
    # -------------------------------
    # MAGEN
    # -------------------------------
    "27631016099": ClientProfile(
        client_code="MAGEN",
        business_msisdn="27631016099",
        admin_numbers=_ADMIN_ALLOWLIST,
        enabled_modules=[
            "inspection",
            "vehicle_inspection",
        ],
    ),

    # -------------------------------
    # GALITOS
    # -------------------------------
    "27735534607": ClientProfile(
        client_code="GALITOS",
        business_msisdn="27735534607",
        admin_numbers=_ADMIN_ALLOWLIST,
        enabled_modules=[
            "orders",
            "inspection",
            "survey",
            "feedback",
            "broadcast",
        ],
    ),
}


# -------------------------------------------------
# Public resolver
# -------------------------------------------------

def get_client_profile(business_msisdn: str) -> Optional[ClientProfile]:
    """
    Resolve client profile by business MSISDN.
    """
    return _PROFILES.get(business_msisdn)
