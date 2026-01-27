from __future__ import annotations

"""
File: app/storage/s3_evidence_store.py
Project: KLResolute WhatsApp SaaS MVP

Purpose:
Minimal, backend-only S3 access for immutable inspection evidence (photos + PDFs).

LOCKED RULES:
- Backend-only access (no presigned/public links)
- Objects are immutable once written
- DB stores metadata + S3 object keys
- Single bucket per environment
"""

import os
from typing import BinaryIO, Optional

import boto3
from botocore.exceptions import ClientError


class S3EvidenceStore:
    def __init__(self) -> None:
        bucket = os.getenv("S3_EVIDENCE_BUCKET")
        region = os.getenv("AWS_REGION")

        if not bucket:
            raise RuntimeError("S3_EVIDENCE_BUCKET is not set")
        if not region:
            raise RuntimeError("AWS_REGION is not set")

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def put_bytes(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> None:
        """
        Write bytes to S3 at a fixed key.
        Caller is responsible for ensuring immutability (write-once).
        """
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_stream(self, *, key: str) -> BinaryIO:
        """
        Read an object as a streaming body.
        Intended for admin PDF in-browser viewing.
        """
        response = self.client.get_object(
            Bucket=self.bucket,
            Key=key,
        )
        return response["Body"]

    def head(self, *, key: str) -> bool:
        """
        Check whether an object exists.
        """
        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=key,
            )
            return True
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise
