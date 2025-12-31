"""
File: app/outbound/meta.py
Path: app/outbound/meta.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Meta WhatsApp Cloud API client.
Supports:
- Session messages (free text)
- Generic business update template
"""

from __future__ import annotations

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
    # SESSION MESSAGE (admin + operational SEND)
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

    # ---------------------------------------------------------
    # TEMPLATE MESSAGE (BUSINESS UPDATE)
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

    def send_generic_business_update_template(
        self, *, to_msisdn: str, blob_text: str
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
"""
File: app/outbound/meta.py
Path: app/outbound/meta.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
Meta WhatsApp Cloud API client.
Supports:
- Session messages (free text)
- Generic business update template
"""

from __future__ import annotations

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
    # SESSION MESSAGE (admin + operational SEND)
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

    # ---------------------------------------------------------
    # TEMPLATE MESSAGE (BUSINESS UPDATE)
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

    def send_generic_business_update_template(
        self, *, to_msisdn: str, blob_text: str
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
