import logging
import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from dotenv import load_dotenv, set_key

# Determine data directory (defaults to /workspace for RunPod network storage)
DATA_DIR = Path(os.environ.get("DATA_DIR", "/workspace"))
if not DATA_DIR.is_absolute():
    DATA_DIR = (Path(__file__).parent / DATA_DIR).resolve()

# Ensure data directory exists before loading .env
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load .env file from data directory (persisted on RunPod network storage)
# Use override=False so environment variables (e.g., from RunPod) take priority
ENV_PATH = DATA_DIR / ".env"
load_dotenv(ENV_PATH, override=False)


def ensure_admin_password() -> str:
    """Ensure ADMIN_PASSWORD exists, generate if not."""
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        password = secrets.token_urlsafe(16)
        # Create .env if it doesn't exist
        if not ENV_PATH.exists():
            ENV_PATH.touch()
        set_key(str(ENV_PATH), "ADMIN_PASSWORD", password)
        # Store flag to show password was just generated
        os.environ["_GENSELFIE_NEW_PASSWORD"] = "1"
    return password


def get_runpod_proxy_url(port: int = 8000) -> str | None:
    """Get the expected RunPod proxy URL if running on RunPod.
    
    Returns the proxy URL based on RUNPOD_POD_ID, or None if not on RunPod.
    """
    pod_id = os.getenv("RUNPOD_POD_ID")
    if pod_id:
        return f"https://{pod_id}-{port}.proxy.runpod.net"
    return None


def is_on_runpod() -> bool:
    """Check if running on RunPod."""
    return os.getenv("RUNPOD_POD_ID") is not None


class Settings(BaseSettings):
    # App settings
    app_name: str = "GenSelfie"
    debug: bool = False
    verbose: bool = False
    
    # Admin
    admin_password: str = ""
    
    # ComfyUI
    comfyui_url: str = "http://localhost:8188"
    
    @field_validator('comfyui_url', mode='after')
    @classmethod
    def ensure_url_scheme(cls, v: str) -> str:
        """Ensure URL has http:// or https:// prefix."""
        if v and not v.startswith(('http://', 'https://')):
            return f'http://{v}'
        return v
    
    # Stripe (optional)
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    
    # LNbits (optional)
    lnbits_url: str = ""
    lnbits_api_key: str = ""
    
    # Public URL for Stripe redirects (required on RunPod)
    public_url: str = ""
    
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
    
    model_config = {
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": False,
    }


# Initialize settings
# Environment variables are already loaded by load_dotenv() above
# pydantic-settings will read from os.environ which has the merged values
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
