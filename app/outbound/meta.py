from __future__ import annotations

"""
File: app/outbound/meta.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Meta WhatsApp Cloud API client.

Supports:
- Session text messages
- Generic business update template
- Image messages
- Interactive button messages

Hardening:
- Strong payload validation
- Explicit Meta failure logging
- Raw response logging
- Defensive guard rails
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging
import requests

from app.outbound.settings import MetaWhatsAppSettings

# ==================================================
# Logging
# ==================================================
logger = logging.getLogger("meta_outbound")


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

        if not settings:
            raise MetaWhatsAppError("Meta settings missing")

        if not settings.access_token:
            raise MetaWhatsAppError("Meta access token missing")

        if not settings.messages_url:
            raise MetaWhatsAppError("Meta messages_url missing")

        self._settings = settings
        self._session = session or requests.Session()

        logger.info(
            "META_CLIENT_INIT | phone_number_id=%s",
            getattr(settings, "phone_number_id", None),
        )

    # ---------------------------------------------------------
    # SESSION MESSAGE
    # ---------------------------------------------------------
    def send_session_message(self, *, to_msisdn: str, text: str) -> MetaSendResult:

        if not to_msisdn:
            raise MetaWhatsAppError("to_msisdn required")

        if not text:
            raise MetaWhatsAppError("Session message text cannot be empty")

        logger.info(
            "META_SEND_SESSION | to=%s | chars=%s",
            to_msisdn,
            len(text),
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "text",
            "text": {"body": text},
        }

        return self._post(payload, "SESSION")

    # ---------------------------------------------------------
    # IMAGE MESSAGE
    # ---------------------------------------------------------
    def send_image_message(
        self,
        *,
        to_msisdn: str,
        media_id: str,
        caption: Optional[str] = None,
    ) -> MetaSendResult:

        if not to_msisdn:
            raise MetaWhatsAppError("to_msisdn required")

        if not media_id:
            raise MetaWhatsAppError("media_id required")

        logger.info(
            "META_SEND_IMAGE | to=%s | has_caption=%s",
            to_msisdn,
            bool(caption),
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "image",
            "image": {"id": media_id},
        }

        if caption:
            payload["image"]["caption"] = caption

        return self._post(payload, "IMAGE")

    # ---------------------------------------------------------
    # TEMPLATE MESSAGE
    # ---------------------------------------------------------
    def send_template(
        self,
        *,
        to_msisdn: str,
        template_name: str,
        language_code: str = "en_US",
        body_params: Optional[list[str]] = None,
    ) -> MetaSendResult:

        if not to_msisdn:
            raise MetaWhatsAppError("to_msisdn required")

        if not template_name:
            raise MetaWhatsAppError("template_name required")

        logger.info(
            "META_SEND_TEMPLATE | to=%s | template=%s | has_params=%s",
            to_msisdn,
            template_name,
            bool(body_params),
        )

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
                    "parameters": [
                        {"type": "text", "text": str(p)} for p in body_params
                    ],
                }
            ]

        return self._post(payload, f"TEMPLATE:{template_name}")

    def send_generic_business_update_template(
        self,
        *,
        to_msisdn: str,
        blob_text: str,
    ) -> MetaSendResult:

        if not blob_text:
            raise MetaWhatsAppError("blob_text cannot be empty")

        if len(blob_text) > 900:
            raise MetaWhatsAppError("blob_text exceeds 900 characters")

        return self.send_template(
            to_msisdn=to_msisdn,
            template_name="generic_business_update",
            language_code="en_US",
            body_params=[blob_text],
        )

    # ---------------------------------------------------------
    # INTERACTIVE BUTTON MESSAGE
    # ---------------------------------------------------------
    def send_interactive_button_message(
        self,
        *,
        to_msisdn: str,
        body_text: str,
        buttons: list[dict],
        header_text: Optional[str] = None,
    ) -> MetaSendResult:

        if not to_msisdn:
            raise MetaWhatsAppError("to_msisdn required")

        if not body_text:
            raise MetaWhatsAppError("body_text required")

        if not buttons or len(buttons) > 3:
            raise MetaWhatsAppError("1–3 buttons required")

        logger.info(
            "META_SEND_INTERACTIVE | to=%s | buttons=%s",
            to_msisdn,
            len(buttons),
        )

        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": b["id"],
                                "title": b["title"],
                            },
                        }
                        for b in buttons
                    ]
                },
            },
        }

        if header_text:
            payload["interactive"]["header"] = {
                "type": "text",
                "text": header_text,
            }

        return self._post(payload, "INTERACTIVE")

    # ---------------------------------------------------------
    # INTERNAL POST
    # ---------------------------------------------------------
    def _post(self, payload: Dict[str, Any], label: str) -> MetaSendResult:

        headers = {
            "Authorization": f"Bearer {self._settings.access_token}",
            "Content-Type": "application/json",
        }

        logger.info(
            "META_HTTP_POST | type=%s | url=%s",
            label,
            self._settings.messages_url,
        )

        try:
            resp = self._session.post(
                self._settings.messages_url,
                json=payload,
                headers=headers,
                timeout=30,
            )
        except Exception as exc:
            logger.error(
                "META_HTTP_EXCEPTION | type=%s | error=%s",
                label,
                exc,
                exc_info=True,
            )
            raise

        raw_text = resp.text

        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": raw_text}

        if not (200 <= resp.status_code < 300):
            logger.error(
                "META_HTTP_ERROR | type=%s | status=%s | response=%s",
                label,
                resp.status_code,
                data,
            )
            logger.error(
                "META_RAW_RESPONSE | type=%s | raw=%s",
                label,
                raw_text,
            )
        else:
            logger.info(
                "META_HTTP_OK | type=%s | status=%s",
                label,
                resp.status_code,
            )

        return MetaSendResult(
            ok=200 <= resp.status_code < 300,
            status_code=resp.status_code,
            response_json=data,
        )
