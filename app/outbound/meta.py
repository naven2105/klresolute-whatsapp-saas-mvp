from __future__ import annotations

"""
File: app/outbound/meta.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Meta WhatsApp Cloud API client.

Supports:
- Session text messages
- Template messages (broadcast text)
- Image messages (admin broadcast image)
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests

from app.outbound.settings import MetaWhatsAppSettings


class MetaWhatsAppError(RuntimeError):
    pass


@dataclass(frozen=True)
class MetaSendResult:
    ok: bool
    status_code: int
    response_json: Dict[str, Any]


class MetaWhatsAppClient:
    def __init__(
        self,
        settings: MetaWhatsAppSettings,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._settings = settings
        self._session = session or requests.Session()

    # ---------------------------------------------------------
    # SESSION MESSAGE (admin + SEND)
    # ---------------------------------------------------------
    def send_session_message(self, *, to_msisdn: str, text: str) -> MetaSendResult:
        if not text:
            raise MetaWhatsAppError("Session message text cannot be empty")

        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "text",
            "text": {"body": text},
        }

        return self._post(payload)

    # ---------------------------------------------------------
    # IMAGE MESSAGE (admin broadcast image)
    # ---------------------------------------------------------
    def send_image(
        self,
        *,
        to_msisdn: str,
        media_id: str,
        caption: Optional[str] = None,
    ) -> MetaSendResult:
        if not media_id:
            raise MetaWhatsAppError("media_id is required")

        image_payload: Dict[str, Any] = {"id": media_id}
        if caption:
            image_payload["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "image",
            "image": image_payload,
        }

        return self._post(payload)

    # ---------------------------------------------------------
    # TEMPLATE MESSAGE (broadcast text)
    # ---------------------------------------------------------
    def send_template(
        self,
        *,
        to_msisdn: str,
        template_name: str,
        language_code: str = "en_US",
        body_params: Optional[list[str]] = None,
    ) -> MetaSendResult:
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }

        if body_params:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in body_params],
                }
            ]

        return self._post(payload)

    def send_generic_business_update_template(
        self,
        *,
        to_msisdn: str,
        blob_text: str,
    ) -> MetaSendResult:
        if not blob_text:
            raise MetaWhatsAppError("blob_text cannot be empty")

        return self.send_template(
            to_msisdn=to_msisdn,
            template_name="generic_business_update",
            body_params=[blob_text],
        )

    # ---------------------------------------------------------
    # INTERNAL POST
    # ---------------------------------------------------------
    def _post(self, payload: Dict[str, Any]) -> MetaSendResult:
        headers = {
            "Authorization": f"Bearer {self._settings.access_token}",
            "Content-Type": "application/json",
        }

        resp = self._session.post(
            self._settings.messages_url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text}

        return MetaSendResult(
            ok=200 <= resp.status_code < 300,
            status_code=resp.status_code,
            response_json=data,
        )
