import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv, set_key

# Load .env file
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)


def ensure_admin_password() -> str:
    """Ensure ADMIN_PASSWORD exists, generate if not."""
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        password = secrets.token_urlsafe(16)
        # Create .env if it doesn't exist
        if not ENV_PATH.exists():
            ENV_PATH.touch()
        set_key(str(ENV_PATH), "ADMIN_PASSWORD", password)
        print(f"Generated new ADMIN_PASSWORD: {password}")
        print("Please save this password - it's stored in .env")
    return password


class Settings(BaseSettings):
    # App settings
    app_name: str = "GenSelfie"
    debug: bool = False
    
    # Admin
    admin_password: str = ""
    
    # ComfyUI
    comfyui_url: str = "http://localhost:8188"
    
    # Stripe (optional)
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    
    # LNbits (optional)
    lnbits_url: str = ""
    lnbits_api_key: str = ""
    
    # Paths
    base_dir: Path = Path(__file__).parent
    upload_dir: Path = Path(__file__).parent / "static" / "uploads"
    database_url: str = "sqlite+aiosqlite:///./genselfie.db"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


# Initialize settings
_admin_password = ensure_admin_password()
settings = Settings(admin_password=_admin_password)

# Ensure upload directory exists
settings.upload_dir.mkdir(parents=True, exist_ok=True)
