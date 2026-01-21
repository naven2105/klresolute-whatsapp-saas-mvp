from __future__ import annotations

"""
File: app/outbound/meta.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Meta WhatsApp Cloud API client.

Supports:
- Session text messages (admin confirmations, SEND)
- Generic business update template (broadcast + admin notifications)
- Image messages using existing Meta media_id
- Interactive button messages (surveys)
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
        self._settings = settings
        self._session = session or requests.Session()

    # ---------------------------------------------------------
    # SESSION MESSAGE (admin + SEND command)
    # ---------------------------------------------------------
    def send_session_message(self, *, to_msisdn: str, text: str) -> MetaSendResult:
        if not text:
            raise MetaWhatsAppError("Session message text cannot be empty")

        logger.info("META_SEND_SESSION | to=%s | chars=%s", to_msisdn, len(text))

        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "text",
            "text": {"body": text},
        }

        return self._post(payload, "SESSION")

    # ---------------------------------------------------------
    # IMAGE MESSAGE (admin image broadcast / specials)
    # ---------------------------------------------------------
    def send_image_message(
        self,
        *,
        to_msisdn: str,
        media_id: str,
        caption: Optional[str] = None,
    ) -> MetaSendResult:
        if not media_id:
            raise MetaWhatsAppError("media_id is required for image send")

        logger.info(
            "META_SEND_IMAGE | to=%s | caption=%r",
            to_msisdn,
            caption,
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
    # TEMPLATE MESSAGE (approved Meta templates)
    # ---------------------------------------------------------
    def send_template(
        self,
        *,
        to_msisdn: str,
        template_name: str,
        language_code: str = "en_US",
        body_params: Optional[list[str]] = None,
    ) -> MetaSendResult:
        logger.info(
            "META_SEND_TEMPLATE | to=%s | template=%s",
            to_msisdn,
            template_name,
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
                    "parameters": [{"type": "text", "text": p} for p in body_params],
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
            raise MetaWhatsAppError("blob_text too long")

        return self.send_template(
            to_msisdn=to_msisdn,
            template_name="generic_business_update",
            language_code="en_US",
            body_params=[blob_text],
        )

    # ---------------------------------------------------------
    # INTERACTIVE BUTTON MESSAGE (surveys)
    # ---------------------------------------------------------
    def send_interactive_button_message(
        self,
        *,
        to_msisdn: str,
        body_text: str,
        buttons: list[dict],
        header_text: Optional[str] = None,
    ) -> MetaSendResult:
        if not body_text:
            raise MetaWhatsAppError("body_text cannot be empty")

        if not buttons or len(buttons) > 3:
            raise MetaWhatsAppError("buttons must contain 1 to 3 items")

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
    # INTERNAL POST (single exit point)
    # ---------------------------------------------------------
    def _post(self, payload: Dict[str, Any], label: str) -> MetaSendResult:
        headers = {
            "Authorization": f"Bearer {self._settings.access_token}",
            "Content-Type": "application/json",
        }

        try:
            resp = self._session.post(
                self._settings.messages_url,
                json=payload,
                headers=headers,
                timeout=30,
            )
        except Exception as exc:
            logger.error(
                "META_HTTP_FAIL | type=%s | error=%s",
                label,
                exc,
                exc_info=True,
            )
            raise

        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text}

        if not (200 <= resp.status_code < 300):
            logger.error(
                "META_HTTP_ERROR | type=%s | status=%s | response=%s",
                label,
                resp.status_code,
                data,
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
