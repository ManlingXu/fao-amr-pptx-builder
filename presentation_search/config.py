from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    knowledge_provider: Literal["local", "sharepoint"] = "local"
    local_presentation_path: Path = Path("./data/presentations")
    drafts_path: Path = Path("./data/drafts")
    auth_mode: Literal["local_demo", "api_key", "entra"] = "api_key"
    admin_api_key: str = ""
    copilot_api_key: str = ""
    entra_audience: str = ""
    entra_allowed_roles: str = ""
    entra_allowed_groups: str = ""

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    sharepoint_drive_id: str = ""
    sharepoint_folder_item_id: str = ""
    sharepoint_cache_path: Path = Path("./data/sharepoint-cache")
    sharepoint_output_drive_id: str = ""
    sharepoint_output_folder_item_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
