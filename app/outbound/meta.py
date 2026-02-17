from __future__ import annotations

"""
File: app/outbound/meta.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Meta WhatsApp Cloud API client.

Supports:
- Session text messages
- Templates
- Image messages
- Interactive buttons
- Media download (for inspection module)

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

    # =========================================================
    # 🔽 MEDIA DOWNLOAD (NEW)
    # =========================================================
    def download_media(self, media_id: str) -> bytes:
        """
        Download media bytes from Meta Cloud API.

        Flow:
        1) GET media metadata (returns temporary URL)
        2) GET binary using returned URL with Bearer auth
        """

        if not media_id:
            raise MetaWhatsAppError("media_id required for download")

        logger.info("META_MEDIA_DOWNLOAD_START | media_id=%s", media_id)

        headers = {
            "Authorization": f"Bearer {self._settings.access_token}",
        }

        # Step 1: Resolve media URL
        media_meta_url = f"https://graph.facebook.com/v20.0/{media_id}"

        try:
            meta_resp = self._session.get(
                media_meta_url,
                headers=headers,
                timeout=30,
            )
        except Exception as exc:
            logger.error(
                "META_MEDIA_META_HTTP_EXCEPTION | media_id=%s | error=%s",
                media_id,
                exc,
                exc_info=True,
            )
            raise

        if meta_resp.status_code != 200:
            logger.error(
                "META_MEDIA_META_HTTP_ERROR | media_id=%s | status=%s | body=%s",
                media_id,
                meta_resp.status_code,
                meta_resp.text,
            )
            raise MetaWhatsAppError("Failed to resolve media URL")

        meta_json = meta_resp.json()
        media_url = meta_json.get("url")

        if not media_url:
            logger.error(
                "META_MEDIA_META_NO_URL | media_id=%s | response=%s",
                media_id,
                meta_json,
            )
            raise MetaWhatsAppError("Media URL missing from Meta response")

        logger.info(
            "META_MEDIA_URL_RESOLVED | media_id=%s",
            media_id,
        )

        # Step 2: Download binary
        try:
            binary_resp = self._session.get(
                media_url,
                headers=headers,
                timeout=60,
            )
        except Exception as exc:
            logger.error(
                "META_MEDIA_BINARY_HTTP_EXCEPTION | media_id=%s | error=%s",
                media_id,
                exc,
                exc_info=True,
            )
            raise

        if binary_resp.status_code != 200:
            logger.error(
                "META_MEDIA_BINARY_HTTP_ERROR | media_id=%s | status=%s",
                media_id,
                binary_resp.status_code,
            )
            raise MetaWhatsAppError("Failed to download media binary")

        if not binary_resp.content:
            logger.error(
                "META_MEDIA_BINARY_EMPTY | media_id=%s",
                media_id,
            )
            raise MetaWhatsAppError("Downloaded media is empty")

        logger.info(
            "META_MEDIA_DOWNLOAD_SUCCESS | media_id=%s | bytes=%s",
            media_id,
            len(binary_resp.content),
        )

        return binary_resp.content

    # =========================================================
    # SESSION MESSAGE
    # =========================================================
    def send_session_message(self, *, to_msisdn: str, text: str) -> MetaSendResult:

        if not to_msisdn:
            raise MetaWhatsAppError("to_msisdn required")

        if not text:
            raise MetaWhatsAppError("Session message text cannot be empty")

        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "text",
            "text": {"body": text},
        }

        return self._post(payload, "SESSION")

    # =========================================================
    # IMAGE MESSAGE
    # =========================================================
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

        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "image",
            "image": {"id": media_id},
        }

        if caption:
            payload["image"]["caption"] = caption

        return self._post(payload, "IMAGE")

    # =========================================================
    # TEMPLATE MESSAGE
    # =========================================================
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

    # =========================================================
    # INTERNAL POST
    # =========================================================
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
