from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.auth.manager import AuthManager
    from src.config.env_store import EnvStore
    from src.config.profiles import ProfileManager
    from src.core.catalog_service import CatalogService
    from src.core.workflow import ReservationWorkflow


@dataclass
class AppServices:
    workflow: "ReservationWorkflow | None" = None
    catalog_service: "CatalogService | None" = None


@dataclass
class CommandContext:
    services: AppServices
    auth_manager: "AuthManager"
    profile_manager: "ProfileManager"
    env_store: "EnvStore | None" = None
    active_profile: str = "default"
    runtime_environ: dict[str, str] = field(default_factory=dict)
