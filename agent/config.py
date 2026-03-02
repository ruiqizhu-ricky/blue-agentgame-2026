# Configuration: config.json (project root) + env override
import json
import os
from pathlib import Path

def _load_config_file():
    """Load config.json from project root (cwd or parent of agent/)."""
    cwd = Path.cwd()
    candidates = [
        cwd / "config.json",
        Path(__file__).resolve().parent.parent / "config.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
    return {}

_raw = _load_config_file()

def _get(key: str, env_key: str, default, coerce=str):
    """File value first, then env, then default. Coerce to int if needed."""
    v = _raw.get(key)
    if v is not None and v != "":
        if coerce is int:
            return int(v)
        return coerce(v)
    v = os.environ.get(env_key)
    if v is not None and v != "":
        if coerce is int:
            return int(v)
        return coerce(v)
    return default

SIMULATION_HOST = _get("simulation_host", "SIMULATION_HOST", "127.0.0.1")
SIMULATION_PORT = _get("simulation_port", "SIMULATION_PORT", 8080, coerce=int)
USER_ID = _get("user_id", "USER_ID", "test_user")
API_TIMEOUT = _get("api_timeout", "API_TIMEOUT", 5, coerce=int)
MAX_HOUSES = _get("max_houses", "MAX_HOUSES", 5, coerce=int)
MAX_HISTORY_TURNS = _get("max_history_turns", "MAX_HISTORY_TURNS", 6, coerce=int)
LLM_API_BASE = _get("llm_api_base", "LLM_API_BASE", "")
LLM_API_KEY = _get("llm_api_key", "LLM_API_KEY", "")
LLM_MODEL = _get("llm_model", "LLM_MODEL", "qwen3-32b")
SERVER_PORT = _get("server_port", "PORT", 8000, coerce=int)

BASE_URL = f"http://{SIMULATION_HOST}:{SIMULATION_PORT}"
HEADERS_WITH_USER = {"X-User-ID": USER_ID}
HEADERS_NO_USER = {}
