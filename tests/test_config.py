import pytest
from pydantic import ValidationError

from services.api.app.config import Settings


def _production_settings(**overrides):
    data = {
        "app_env": "uat",
        "database_url": "postgresql+asyncpg://user:pass@example.com:5432/app",
        "jwt_secret": "x" * 32,
        "cors_origins": "https://wisebasket.example",
    }
    data.update(overrides)
    return Settings(**data)


def test_uat_settings_allow_explicit_local_qa_origins_but_drop_wildcard():
    settings = _production_settings(
        cors_origins=(
            "http://localhost:3000,"
            "https://wisebasket.example,"
            "http://127.0.0.1:5173,"
            "*"
        )
    )

    assert settings.cors_origins == (
        "http://localhost:3000,https://wisebasket.example,http://127.0.0.1:5173"
    )


def test_production_settings_drop_local_and_wildcard_cors_origins():
    settings = _production_settings(
        app_env="production",
        cors_origins="http://localhost:3000,http://127.0.0.1:5173,*,https://wisebasket.example",
    )

    assert settings.cors_origins == "https://wisebasket.example"


def test_production_like_settings_still_require_strong_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _production_settings(jwt_secret="change-me")


def test_completed_receipt_reprocessing_is_rejected_outside_qa():
    assert _production_settings(receipt_reprocess_done_uploads=True).receipt_reprocess_done_uploads
    with pytest.raises(ValidationError, match="RECEIPT_REPROCESS_DONE_UPLOADS"):
        _production_settings(app_env="production", receipt_reprocess_done_uploads=True)


@pytest.mark.parametrize("environment,repeat", [
    ("uat", True), ("staging", True), ("production", False), ("prod", False),
    ("development", False), ("test", False),
])
def test_receipt_cache_and_repeat_purchase_defaults(environment, repeat):
    settings = _production_settings(_env_file=None, app_env=environment)
    assert settings.receipt_reprocess_done_uploads is False
    assert settings.receipt_allow_repeat_purchases is repeat


@pytest.mark.parametrize("environment", ["production", "prod", "development", "unknown"])
def test_repeat_purchases_are_rejected_outside_qa(environment):
    with pytest.raises(ValidationError, match="RECEIPT_ALLOW_REPEAT_PURCHASES"):
        _production_settings(_env_file=None, app_env=environment, receipt_allow_repeat_purchases=True)


def test_repeat_purchase_protection_can_be_restored_in_uat():
    assert _production_settings(_env_file=None, receipt_allow_repeat_purchases=False).receipt_allow_repeat_purchases is False


def test_explicit_false_restores_completed_image_reuse_in_uat():
    assert _production_settings(_env_file=None, receipt_reprocess_done_uploads=False).receipt_reprocess_done_uploads is False
