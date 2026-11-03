import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, cast

import aioboto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from services.errors import ServiceError

logger = logging.getLogger(__name__)

REQUIRED_ENV = ("S3_BUCKET","AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")

# aioboto3 reads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from the env.
_session = aioboto3.Session()


class StorageError(ServiceError):
    status_code = 502


def warn_if_unconfigured() -> None:
    for name in REQUIRED_ENV:
        if not os.getenv(name):
            logger.warning("%s is not set; résumé upload will fail until it is", name)


def _bucket() -> str:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise StorageError("S3_BUCKET is not set", status_code=500)
    return bucket


@asynccontextmanager
async def _client() -> AsyncIterator[Any]:
    client_cm = _session.client(
        "s3",
        region_name=os.getenv("AWS_REGION"),
        config=Config(retries={"max_attempts": 3}),
    )
    async with cast(Any, client_cm) as client:
        yield client


async def put(key: str, data: bytes, content_type: str) -> None:
    bucket = _bucket()
    try:
        async with _client() as client:
            await client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Couldn't store %s in S3", key)
        raise StorageError("Couldn't store the résumé, try again") from exc


async def get_bytes(key: str) -> bytes:
    bucket = _bucket()
    try:
        async with _client() as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            return await response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Couldn't read %s from S3", key)
        raise StorageError("Couldn't read the résumé from file storage") from exc
