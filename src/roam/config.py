from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.
    """
    google_maps_api_key: str = Field(..., description="Google Maps Platform API Key")
    
    # Garage/Fleet config path (defaulting to user config dir)
    config_dir: Path = Field(default=Path.home() / ".config" / "roam", description="Directory for local config")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def fleet_config_path(self) -> Path:
        return self.config_dir / "garage.json"

    def ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
try:
    settings = Settings()
except Exception:
    # Allow instantiation without env vars for build/test steps that might mock it
    # Real execution will fail validation if keys are missing
    settings = None # type: ignore
