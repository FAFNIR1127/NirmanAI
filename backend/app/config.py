import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_VERSION_DIR = BASE_DIR / "models" / "risk_engine_v1"
FALLBACK_SQLITE_PATH = BASE_DIR / "database" / "nirman.db"

# Load .env file manually so env vars are available even without python-dotenv
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            _key = _key.strip()
            _val = _val.strip()
            if _key and _key not in os.environ:  # don't override existing shell env vars
                os.environ[_key] = _val

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:hulk@localhost:5432/nirman_db")
