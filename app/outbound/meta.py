"""
File: app/outbound/meta.py

Project: KLResolute WhatsApp SaaS MVP

Purpose:
T-24 Meta WhatsApp gateway (REAL SENDING, GUARDED)

Design rules:
- Never called directly from the webhook
- Safe-by-default: refuses to send unless explicitly enabled
- Allowlist safety: only numbers in allowlist can receive messages
- Any misconfiguration fails safely (no send)

Notes:
- Uses Meta Graph API: POST /{phone_number_id}/messages
- Minimal payload: text messages only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
import json
import urllib.request
import urllib.error

from .gateway import SendGateway, OutboundSendRequest, OutboundSendReceipt, SendStatus


@dataclass(frozen=True)
class MetaSendConfig:
    enabled: bool
    access_token: Optional[str] = None
    phone_number_id: Optional[str] = None
    api_base_url: str = "https://graph.facebook.com/v20.0"
    test_allowlist: Sequence[str] = ()  # e.g. ("27627597357", "27735534607")


class MetaSendGateway(SendGateway):
    def __init__(self, cfg: MetaSendConfig) -> None:
        self._cfg = cfg

    def send_text(self, req: OutboundSendRequest) -> OutboundSendReceipt:
        # Safety lock: must be enabled explicitly
        if not self._cfg.enabled:
            return OutboundSendReceipt.now(
                status=SendStatus.DISABLED,
                detail="MetaSendGateway disabled. No message sent.",
                provider_message_id=None,
            )

        # Allowlist safety (Option 2)
        allow = tuple(n.strip() for n in (self._cfg.test_allowlist or ()) if n and n.strip())
        if allow and req.to_number not in allow:
            return OutboundSendReceipt.now(
                status=SendStatus.DISABLED,
                detail=f"Recipient not in OUTBOUND_TEST_ALLOWLIST. No message sent. to={req.to_number}",
                provider_message_id=None,
            )

        # Required config
        if not self._cfg.access_token or not self._cfg.phone_number_id:
            return OutboundSendReceipt.now(
                status=SendStatus.FAILED,
                detail="MetaSendGateway enabled but missing access_token and/or phone_number_id. No message sent.",
                provider_message_id=None,
            )

        url = f"{self._cfg.api_base_url.rstrip('/')}/{self._cfg.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": req.to_number,
            "type": "text",
            "text": {"body": req.body_text},
        }

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._cfg.access_token}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw) if raw else {}
                except Exception:
                    parsed = {}

                provider_message_id = None
                # Typical response: {"messages":[{"id":"wamid...."}]}
                if isinstance(parsed, dict):
                    msgs = parsed.get("messages")
                    if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
                        provider_message_id = msgs[0].get("id")

                return OutboundSendReceipt.now(
                    status=SendStatus.SENT,
                    detail="Sent via Meta Cloud API",
                    provider_message_id=provider_message_id,
                )

        except urllib.error.HTTPError as e:
            detail = f"Meta HTTPError {getattr(e, 'code', None)}: {e.read().decode('utf-8', errors='replace')}"
            return OutboundSendReceipt.now(
                status=SendStatus.FAILED,
                detail=detail,
                provider_message_id=None,
            )
        except Exception as e:
            return OutboundSendReceipt.now(
                status=SendStatus.FAILED,
                detail=f"Meta send failed: {type(e).__name__}: {e}",
                provider_message_id=None,
            )
