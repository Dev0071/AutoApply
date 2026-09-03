from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    # Required when the API key is identity-linked (the API rejects such
    # requests with a 400 unless the workspace is named). Leave blank for a
    # plain org API key.
    anthropic_workspace_id: str = ""
    browserbase_api_key: str
    database_url: str
    redis_url: str
    s3_bucket: str
    s3_region: str
    fit_threshold_default: int = 70
    vision_loop_max_steps: int = 30
    vision_loop_wait_ms: int = 800
    vision_loop_inter_action_wait_ms: int = 200
    vision_loop_token_budget: int = 150_000

    # Model routing — each stage uses the cheapest model that holds quality.
    vision_model: str = "claude-sonnet-5"
    vision_fallback_model: str = "claude-opus-5"
    tailoring_model: str = "claude-sonnet-5"
    extraction_model: str = "claude-haiku-4-5"
    mapping_model: str = "claude-haiku-4-5"

    # Hybrid navigation: DOM-serialized fill first, vision loop as fallback.
    hybrid_fill_enabled: bool = True

    # Ops guardrails
    browser_mode: str = "browserbase"  # "browserbase" | "local"
    jd_cache_ttl_seconds: int = 86_400
    # Settle time for SPA job boards (Ashby et al.) after DOM content loads
    jd_render_wait_ms: int = 2_000
    max_daily_applications_per_platform: int = 20
    cost_alert_usd: float = 0.50
    screenshot_retention_days: int = 30

    model_config = {"env_file": ".env"}


settings = Settings()
