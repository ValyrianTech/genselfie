import logging
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
    verbose: bool = False
    
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
    base_dir: Path = Path(__file__).parent.resolve()
    
    @property
    def data_dir(self) -> Path:
        data_path = Path(os.environ.get("DATA_DIR", "/workspace"))
        if not data_path.is_absolute():
            return (self.base_dir / data_path).resolve()
        return data_path
    
    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"
    
    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.data_dir}/genselfie.db"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


# Initialize settings
_admin_password = ensure_admin_password()
settings = Settings(admin_password=_admin_password)

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
logger = logging.getLogger("genselfie")


def setup_logging(verbose: bool = False):
    """Configure logging based on verbose flag."""
    # Set root logger to INFO to avoid noisy library debug messages
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Only enable DEBUG for our app logger when verbose
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    else:
        logger.setLevel(logging.INFO)
