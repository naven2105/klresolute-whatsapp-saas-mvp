from __future__ import annotations

"""
File: app/profiles/client_profile.py
Path: app/profiles/client_profile.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Client profile definitions.

Rules (LOCKED):
- Clients are configuration, not code forks
- Admin allowlists are client-specific
- Used by dispatcher, broadcast, inspections, jobs
"""

from dataclasses import dataclass
from typing import List


# -------------------------------------------------------------------
# Client Profile Model
# -------------------------------------------------------------------
@dataclass(frozen=True)
class ClientProfile:
    client_code: str
    business_msisdn: str
    enabled_modules: list[str]
    admin_numbers: list[str]


# -------------------------------------------------------------------
# ADMIN ALLOWLISTS (CLIENT-SPECIFIC)
# -------------------------------------------------------------------

_MAGEN_ADMIN_NUMBERS = [
    "27627597357",
]

_GALITOS_ADMIN_NUMBERS = [
    "27627597357",
]


# -------------------------------------------------------------------
# CLIENT REGISTRY
# -------------------------------------------------------------------
_CLIENT_PROFILES: dict[str, ClientProfile] = {
    "MAGEN": ClientProfile(
        client_code="MAGEN",
        business_msisdn="MAGEN",
        enabled_modules=[
            "inspection",
        ],
        admin_numbers=_MAGEN_ADMIN_NUMBERS,
    ),
    "GALITOS": ClientProfile(
        client_code="GALITOS",
        business_msisdn="GALITOS",
        enabled_modules=[
            "orders",
            "inspection",
        ],
        admin_numbers=_GALITOS_ADMIN_NUMBERS,
    ),
}


# -------------------------------------------------------------------
# Public lookup
# -------------------------------------------------------------------
def get_client_profile(business_msisdn: str) -> ClientProfile | None:
    """
    Resolve client profile by business WhatsApp number.
    """
    return _CLIENT_PROFILES.get(business_msisdn)
