"""
File: app/outbound/factory.py
Path: app/outbound/factory.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
- Provide a single place to construct outbound clients/services
- Reuse a single Meta WhatsApp client instance (singleton-style)

Design rules:
- No business logic here
- Only construction / wiring
"""

from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request

from app.outbound.meta import MetaWhatsAppClient, MetaWhatsAppError
from app.outbound.settings import load_meta_settings


# -------------------------------------------------
# Meta client singleton
# -------------------------------------------------
_meta_client: MetaWhatsAppClient | None = None


def get_meta_client() -> MetaWhatsAppClient:
    global _meta_client
    if _meta_client is None:
        settings = load_meta_settings()
        _meta_client = MetaWhatsAppClient(settings=settings)
    return _meta_client


# -------------------------------------------------
# Optional outbound test routes (MVP only)
# -------------------------------------------------
def register_outbound_routes(app: Flask) -> None:
    bp = Blueprint("outbound", __name__)

    @bp.post("/outbound/test-template")
    def outbound_test_template():
        payload = request.get_json(silent=True) or {}
        to_msisdn = (payload.get("to") or "").strip()
        blob = (payload.get("blob") or "").strip()

        if not to_msisdn:
            return jsonify({"ok": False, "error": "Missing 'to'"}), 400
        if not blob:
            return jsonify({"ok": False, "error": "Missing 'blob'"}), 400

        client = get_meta_client()
        try:
            result = client.send_generic_business_update_template(
                to_msisdn=to_msisdn,
                blob_text=blob,
            )
        except MetaWhatsAppError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

        status = 200 if result.ok else 502
        return jsonify(
            {
                "ok": result.ok,
                "status_code": result.status_code,
                "meta": result.response_json,
            }
        ), status

    app.register_blueprint(bp)
