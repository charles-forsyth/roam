from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, BaseModel
from typing import Dict, Optional
import json


class VehicleConfig(BaseModel):
    mode: str
    engine: Optional[str] = None
    avoid_tolls: bool = False
    avoid_highways: bool = False
    avoid_ferries: bool = False


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.
    """

    google_maps_api_key: str = Field(..., description="Google Maps Platform API Key")

    # Garage/Fleet config path (defaulting to user config dir)
    config_dir: Path = Field(
        default=Path.home() / ".config" / "roam",
        description="Directory for local config",
    )

    model_config = SettingsConfigDict(
        env_file=[".env", str(Path.home() / ".config" / "roam" / ".env")],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def fleet_config_path(self) -> Path:
        return self.config_dir / "garage.json"

    @property
    def places_config_path(self) -> Path:
        return self.config_dir / "places.json"

    def ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

    # --- Garage ---
    def load_garage(self) -> Dict[str, VehicleConfig]:
        if not self.fleet_config_path.exists():
            return {}
        try:
            data = json.loads(self.fleet_config_path.read_text())
            return {k: VehicleConfig(**v) for k, v in data.items()}
        except Exception:
            return {}

    def save_garage(self, garage: Dict[str, VehicleConfig]):
        self.ensure_config_dir()
        data = {k: v.model_dump(exclude_none=True) for k, v in garage.items()}
        self.fleet_config_path.write_text(json.dumps(data, indent=2))

    # --- Places ---
    def load_places(self) -> Dict[str, str]:
        if not self.places_config_path.exists():
            return {}
        try:
            return json.loads(self.places_config_path.read_text())
        except Exception:
            return {}

    def save_places(self, places: Dict[str, str]):
        self.ensure_config_dir()
        self.places_config_path.write_text(json.dumps(places, indent=2))


# Global settings instance
try:
    settings = Settings()
except Exception:
    settings = None  # type: ignore