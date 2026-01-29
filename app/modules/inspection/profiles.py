from __future__ import annotations

"""
File: app/modules/inspection/profiles.py
Path: app/modules/inspection/profiles.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Inspection profile definitions (pure configuration).
"""

INSPECTION_PROFILES = {
    # ----------------------------------
    # SITE INSPECTION (Security / Retail)
    # ----------------------------------
    "SITE_STANDARD": {
        "inspection_type": "SITE",
        "requires_asset": False,
        "requires_pre_post": False,
        "requires_gps": True,
        "areas": [
            {"code": "OUT", "label": "Outside", "min_photos": 1},
            {"code": "IN", "label": "Inside", "min_photos": 1},
        ],
        "rules": {
            "min_total_photos": 2,
            "auto_start_on_first_media": True,
            "auto_close_timeout_minutes": 5,
        },
        "templates": {
            "completion": "magen_inspection_completed",
        },
    },

    # ----------------------------------
    # VEHICLE INSPECTION
    # ----------------------------------
    "VEHICLE_STANDARD": {
        "inspection_type": "VEHICLE",
        "requires_asset": True,
        "requires_pre_post": True,
        "requires_gps": False,
        "areas": [
            {"code": "EXT", "label": "Vehicle Exterior", "min_photos": 2},
            {"code": "INT", "label": "Vehicle Interior", "min_photos": 1},
        ],
        "rules": {
            "min_total_photos": 3,
            "auto_start_on_first_media": True,
            "auto_close_timeout_minutes": 10,
        },
        "templates": {
            "completion": "magen_inspection_completed",
        },
    },
}