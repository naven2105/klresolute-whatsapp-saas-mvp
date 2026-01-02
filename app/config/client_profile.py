"""
client_profile.py

Client-specific business details.
This file is safe to edit per customer.
No logic. No imports from handlers.
"""

BUSINESS_NAME = "Your Store Name"

TRADING_HOURS = (
    "⏰ Trading Hours:\n"
    "Mon–Sat: 8am – 6pm\n"
    "Sun & Public Holidays: Closed"
)

ADDRESS = (
    "📍 Address:\n"
    "123 Main Road\n"
    "Your Area"
)

CONTACT = (
    "📞 Contact:\n"
    "081 000 0000"
)

ABOUT_TEXT = (
    f"🏪 {BUSINESS_NAME}\n\n"
    f"{TRADING_HOURS}\n\n"
    f"{ADDRESS}\n\n"
    f"{CONTACT}"
)
