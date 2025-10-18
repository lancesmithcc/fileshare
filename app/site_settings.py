from __future__ import annotations

from typing import Dict

from .database import db
from .models import SiteSetting

DEFAULT_SETTINGS: Dict[str, str] = {
    "site_title": "Neo Druidic Society",
    "hero_title": "Neo Druidic Society",
    "hero_subtitle": "A communal hearth for modern mystics, nature stewards, and ritual makers.",
    "landing_description": (
        "Gather with fellow seekers, share reflections from the wild, and keep rituals alive in community."
    ),
    "custom_css": "",
}

ALLOWED_SETTING_KEYS = set(DEFAULT_SETTINGS.keys())


def get_site_settings() -> Dict[str, str]:
    """Return site settings merged with defaults."""
    payload = DEFAULT_SETTINGS.copy()
    for setting in SiteSetting.query.all():
        payload[setting.key] = setting.value
    return payload


def get_setting(key: str, default: str | None = None) -> str | None:
    """Fetch an individual setting; fall back to defaults."""
    record = SiteSetting.query.filter_by(key=key).one_or_none()
    if record:
        return record.value
    if default is not None:
        return default
    return DEFAULT_SETTINGS.get(key)


def update_settings(updates: Dict[str, str]) -> None:
    """Persist the provided site settings, limited to the allowed keys."""
    dirty = False
    for key, value in updates.items():
        if key not in ALLOWED_SETTING_KEYS:
            continue
        setting = SiteSetting.query.filter_by(key=key).one_or_none()
        if not setting:
            setting = SiteSetting(key=key)
        if setting.value != value:
            setting.value = value
            db.session.add(setting)
            dirty = True
    if dirty:
        db.session.commit()
