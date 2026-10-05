"""Application settings. All secrets come from environment variables.

Local dev: create .env with local Docker values.
Production (Railway): set the same names as private service environment
variables. .env.example is a local-dev template, not production defaults.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App / infra ---
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket"
    cors_origins: str = "http://localhost:3000,http://localhost:8081,http://localhost:5173,http://127.0.0.1:5173"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # --- DeepSeek (receipt interpretation only, never planner decisions) ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    # deepseek-chat (non-reasoning): the reasoning variants spend the whole
    # max_tokens budget on chain-of-thought and return empty content for
    # structured tasks like meal-slot JSON (verified 2026-08-27).
    deepseek_model: str = "deepseek-chat"
    llm_enabled: bool = False
    llm_timeout_s: float = 30.0

    # --- Geoapify (manual typed location search) ---
    geoapify_api_key: str = ""
    geoapify_base_url: str = "https://api.geoapify.com/v1/geocode/autocomplete"
    geoapify_timeout_s: float = 5.0

    # --- Epic 6: receipt capture pipeline ---
    # API -> Celery worker (extract_receipt_task) -> inference service.
    # redis_url set => dispatch by task name; empty => inline extraction in a
    # FastAPI BackgroundTask (local dev / tests without a broker).
    redis_url: str = ""
    # Inference service base URL (PaddleOCR). Empty => receipt
    # endpoints still accept uploads but extraction fails with a clear error.
    # Railway private DNS example: http://inference-uat.railway.internal:8080
    inference_url: str = ""
    inference_timeout_s: float = 180.0
    receipt_uploads_per_day: int = 10
    receipt_processing_deadline_s: int = 240
    # Reuse completed analysis everywhere unless QA explicitly requests a
    # paid re-analysis. Active uploads always remain idempotent.
    receipt_reprocess_done_uploads: bool = False
    # Internal QA can upload a confirmed image again as a new test purchase,
    # reusing saved review rows without running OCR/cloud inference again.
    # Confirming the SAME receipt remains idempotent in every environment.
    receipt_allow_repeat_purchases: bool | None = None
    receipt_cloud_enabled: bool = False
    # Fail a test receipt if the configured cloud provider cannot be used;
    # otherwise the normal local-OCR fallback could look like a model result.
    receipt_cloud_required: bool = False
    receipt_cloud_monthly_budget_usd: float = 10.0
    receipt_cloud_provider: str = "local"  # local | deepseek | kimi | azure
    # Explicit operator acknowledgement after key rotation and a fresh price
    # check. The default path never transmits a receipt to a cloud model.
    receipt_cloud_keys_rotated: bool = False
    receipt_cloud_price_version: str = ""
    kimi_api_key: str = ""
    kimi_model: str = "kimi-k3"
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    azure_document_intelligence_key: str = ""
    azure_document_intelligence_endpoint: str = "https://wisebasket-receipt-resource.cognitiveservices.azure.com/"
    azure_document_intelligence_sku: str = "F0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_security_defaults(self) -> "Settings":
        environment = self.app_env.lower()
        if self.receipt_allow_repeat_purchases is None:
            self.receipt_allow_repeat_purchases = environment in {"uat", "staging"}
        if self.receipt_allow_repeat_purchases and environment not in {"uat", "staging", "test", "testing"}:
            raise ValueError("RECEIPT_ALLOW_REPEAT_PURCHASES is only allowed in UAT/staging/test.")
        if self.receipt_reprocess_done_uploads and environment not in {"uat", "staging", "test", "testing"}:
            raise ValueError("RECEIPT_REPROCESS_DONE_UPLOADS is only allowed in UAT/staging/test.")
        production_like = environment not in {"development", "dev", "test", "testing", "local"}
        if production_like:
            if self.jwt_secret in {"", "change-me"} or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a strong non-default value outside development.")
            if self.database_url == "postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket":
                raise ValueError("DATABASE_URL must be set explicitly outside development.")
            origins = [
                origin.strip().lower()
                for origin in self.cors_origins.split(",")
                if origin.strip()
            ]
            # UAT is intentionally reachable from explicitly configured local
            # Expo Web origins for browser QA. Production still strips every
            # localhost/loopback origin even when it is accidentally supplied.
            unsafe_origins = {"*"}
            origins = [
                origin
                for origin in origins
                if origin not in unsafe_origins
                and (
                    environment not in {"production", "prod"}
                    or (
                        not origin.startswith("http://localhost")
                        and not origin.startswith("http://127.")
                    )
                )
            ]
            self.cors_origins = ",".join(origins)
            if self.access_token_minutes <= 0 or self.refresh_token_days <= 0:
                raise ValueError("Token lifetimes must be positive.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
