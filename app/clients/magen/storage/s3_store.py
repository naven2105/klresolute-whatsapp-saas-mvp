from __future__ import annotations

"""
File: app/clients/magen/storage/s3_store.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Magen-only backend S3 access for immutable inspection evidence.

LOCKED RULES:
- Backend-only access (no presigned/public links)
- Objects are immutable once written
- DB stores metadata + S3 object keys
- Single bucket per environment
- Logging required
"""

import os
import logging
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError, BotoCoreError


logger = logging.getLogger("clients.magen.storage")


class S3EvidenceStore:
    def __init__(self) -> None:
        bucket = os.getenv("S3_EVIDENCE_BUCKET")
        region = os.getenv("AWS_REGION")

        if not bucket:
            logger.critical("S3_EVIDENCE_BUCKET not configured")
            raise RuntimeError("S3_EVIDENCE_BUCKET is not set")

        if not region:
            logger.critical("AWS_REGION not configured")
            raise RuntimeError("AWS_REGION is not set")

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

        logger.info("MAGEN_S3_INIT_SUCCESS | bucket=%s | region=%s", bucket, region)

    # -------------------------------------------------
    # Upload bytes (write-once expected)
    # -------------------------------------------------

    def put_bytes(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> None:
        try:
            logger.info("MAGEN_S3_PUT_START | key=%s", key)

            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )

            logger.info("MAGEN_S3_PUT_SUCCESS | key=%s", key)

        except (ClientError, BotoCoreError):
            logger.exception("MAGEN_S3_PUT_FAIL | key=%s", key)
            raise

    # -------------------------------------------------
    # Stream object (for inline admin viewing)
    # -------------------------------------------------

    def get_stream(self, *, key: str) -> BinaryIO:
        try:
            logger.info("MAGEN_S3_GET_START | key=%s", key)

            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key,
            )

            logger.info("MAGEN_S3_GET_SUCCESS | key=%s", key)

            return response["Body"]

        except (ClientError, BotoCoreError):
            logger.exception("MAGEN_S3_GET_FAIL | key=%s", key)
            raise

    # -------------------------------------------------
    # Existence check
    # -------------------------------------------------

    def head(self, *, key: str) -> bool:
        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=key,
            )
            logger.info("MAGEN_S3_HEAD_EXISTS | key=%s", key)
            return True

        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

            if status == 404:
                logger.warning("MAGEN_S3_HEAD_NOT_FOUND | key=%s", key)
                return False

            logger.exception("MAGEN_S3_HEAD_ERROR | key=%s", key)
            raise
