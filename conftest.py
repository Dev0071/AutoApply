"""
Root conftest: sets dummy env vars before any module is imported,
so config.py doesn't fail-fast during test collection.
Real integration tests that hit live services are gated behind -m integration.
"""
import os

_TEST_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "BROWSERBASE_API_KEY": "test-key",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET": "test-bucket",
    "S3_REGION": "us-east-1",
}

for k, v in _TEST_ENV.items():
    os.environ.setdefault(k, v)
