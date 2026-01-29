from __future__ import annotations

"""
file = app/clients/magen/config.py
Client configuration for MAGEN Security.
No business logic allowed in this file.
"""

CLIENT_CODE = "MAGEN"

ENABLED_MODULES = [
    "inspection",
]

INSPECTION_PROFILES = {
    # Security officer site visits
    "default": "SITE_STANDARD",

    # Vehicle inspections (drivers)
    "vehicle_pre_shift": "VEHICLE_STANDARD",
    "vehicle_post_shift": "VEHICLE_STANDARD",
}
