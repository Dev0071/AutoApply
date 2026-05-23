from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    browserbase_api_key: str
    database_url: str
    redis_url: str
    s3_bucket: str
    s3_region: str
    fit_threshold_default: int = 70
    vision_loop_max_steps: int = 30
    vision_loop_wait_ms: int = 800

    model_config = {"env_file": ".env"}


settings = Settings()
