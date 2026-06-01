"""Configuration services for user settings and runtime data paths."""

from .data_paths import get_data_paths, reset_data_paths_cache
from .settings_schema import (
    AppSettings,
    AppSettingsPatch,
    AppSettingsView,
    LLMConfigView,
    LLMSecrets,
    LLMSettingsUpdate,
    NewGameDefaults,
    RunConfig,
)
from .settings_service import get_settings_service, reset_settings_service_cache
from .presets import (
    DEFAULT_PRESET_ID,
    PresetConfigError,
    get_active_preset_id,
    get_preset_goldfinger_keys,
    get_preset_name_templates,
    get_preset_realm_enum_order,
    get_preset_persona_keys,
    get_preset_realm_order,
    get_preset_sect_ids,
    get_preset_stage_order,
    set_active_preset,
)

__all__ = [
    "AppSettings",
    "AppSettingsPatch",
    "AppSettingsView",
    "LLMConfigView",
    "LLMSecrets",
    "LLMSettingsUpdate",
    "NewGameDefaults",
    "RunConfig",
    "DEFAULT_PRESET_ID",
    "PresetConfigError",
    "get_data_paths",
    "get_active_preset_id",
    "get_preset_goldfinger_keys",
    "get_preset_name_templates",
    "get_preset_realm_enum_order",
    "get_preset_persona_keys",
    "get_preset_realm_order",
    "get_preset_sect_ids",
    "get_preset_stage_order",
    "get_settings_service",
    "reset_data_paths_cache",
    "reset_settings_service_cache",
    "set_active_preset",
]
