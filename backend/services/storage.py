from __future__ import annotations

import io

import boto3
import structlog

from backend.config import settings

log = structlog.get_logger()

_WEBP_QUALITY = 80


def compress_screenshot(png_bytes: bytes, quality: int = _WEBP_QUALITY) -> tuple[bytes, str]:
    """Re-encode a PNG screenshot as WebP for the audit trail.

    WebP at full 1280x800 resolution measures ~2.8x smaller than PNG on real
    ATS form screenshots, with no downscaling — step replay stays legible.
    (JPEG is the wrong choice here: on flat UI screenshots it comes out
    *larger* than PNG.) Returns the original PNG unchanged if Pillow is
    unavailable, the bytes aren't decodable, or WebP somehow encodes larger.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality)
        webp = buf.getvalue()
    except Exception:
        return png_bytes, "png"

    if len(webp) >= len(png_bytes):
        return png_bytes, "png"
    return webp, "webp"


class StorageService:
    def __init__(self):
        self._s3 = boto3.client("s3", region_name=settings.s3_region)
        self._bucket = settings.s3_bucket

    async def upload_screenshot(self, png_bytes: bytes, run_id: str, step: int) -> str:
        body, ext = compress_screenshot(png_bytes)
        key = f"runs/{run_id}/step_{step:03d}.{ext}"
        content_type = "image/webp" if ext == "webp" else "image/png"
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=body, ContentType=content_type)
        url = f"s3://{self._bucket}/{key}"
        log.info("screenshot_uploaded", url=url)
        return url

    def apply_lifecycle_policy(self, days: int | None = None) -> None:
        """Expire audit screenshots after the retention window. Run once per
        environment (idempotent): `make s3-lifecycle`."""
        days = days or settings.screenshot_retention_days
        self._s3.put_bucket_lifecycle_configuration(
            Bucket=self._bucket,
            LifecycleConfiguration={
                "Rules": [{
                    "ID": "expire-run-screenshots",
                    "Filter": {"Prefix": "runs/"},
                    "Status": "Enabled",
                    "Expiration": {"Days": days},
                }]
            },
        )
        log.info("s3_lifecycle_applied", bucket=self._bucket, days=days)

    def presigned_url(self, s3_url: str, expires: int = 3600) -> str:
        key = s3_url.replace(f"s3://{self._bucket}/", "")
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )
