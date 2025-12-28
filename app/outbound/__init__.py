# app/outbound/__init__.py
from .gateway import SendGateway, OutboundSendRequest, OutboundSendReceipt, SendStatus
from .dry_run import DryRunSendGateway
from .factory import OutboundDeliverySettings, build_send_gateway

# Meta gateway intentionally disabled until T-12+
# from .meta import MetaSendGateway, MetaSendConfig   