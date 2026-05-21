import boto3
import structlog

from backend.config import settings

log = structlog.get_logger()


class StorageService:
    def __init__(self):
        self._s3 = boto3.client("s3", region_name=settings.s3_region)
        self._bucket = settings.s3_bucket

    async def upload_screenshot(self, png_bytes: bytes, run_id: str, step: int) -> str:
        key = f"runs/{run_id}/step_{step:03d}.png"
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=png_bytes, ContentType="image/png")
        url = f"s3://{self._bucket}/{key}"
        log.info("screenshot_uploaded", url=url)
        return url

    def presigned_url(self, s3_url: str, expires: int = 3600) -> str:
        key = s3_url.replace(f"s3://{self._bucket}/", "")
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )
