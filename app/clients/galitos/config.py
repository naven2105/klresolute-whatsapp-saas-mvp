from __future__ import annotations

"""
file = app/clients/galitos/config.py
Client configuration for GALITOS.
No business logic allowed in this file.
"""

CLIENT_CODE = "GALITOS"

ENABLED_MODULES = [
    "inspection",
    # future: "orders", "broadcast", "survey"
]

INSPECTION_PROFILES = {
    # Container / kitchen inspections
    "default": "SITE_STANDARD",
}
