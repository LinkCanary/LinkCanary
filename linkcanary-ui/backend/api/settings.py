"""Settings API endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter

from ..config import settings
from ..models.schemas import SettingsSchema

router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTINGS_FILE = settings.data_dir / "settings.json"


def load_user_settings() -> dict:
    """Load user settings from file."""
    if SETTINGS_FILE.exists():
        return json.loads(SETTINGS_FILE.read_text())
    return {}


def save_user_settings(data: dict) -> None:
    """Save user settings to file."""
    settings.ensure_dirs()
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))


@router.get("", response_model=SettingsSchema)
async def get_settings():
    """Get user settings."""
    user_settings = load_user_settings()
    return SettingsSchema(
        default_delay=user_settings.get("default_delay", settings.default_delay),
        default_timeout=user_settings.get("default_timeout", settings.default_timeout),
        default_skip_ok=user_settings.get("default_skip_ok", settings.default_skip_ok),
        default_internal_only=user_settings.get("default_internal_only", settings.default_internal_only),
        report_retention_days=user_settings.get("report_retention_days", settings.report_retention_days),
        max_storage_mb=user_settings.get("max_storage_mb", settings.max_storage_mb),
    )


@router.put("", response_model=SettingsSchema)
async def update_settings(new_settings: SettingsSchema):
    """Update user settings."""
    save_user_settings(new_settings.model_dump())
    return new_settings
