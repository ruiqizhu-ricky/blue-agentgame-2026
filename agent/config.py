# Configuration from environment (contest/judge may inject)
import os

SIMULATION_HOST = os.environ.get("SIMULATION_HOST", "127.0.0.1")
SIMULATION_PORT = os.environ.get("SIMULATION_PORT", "8080")
USER_ID = os.environ.get("USER_ID", "test_user")

BASE_URL = f"http://{SIMULATION_HOST}:{SIMULATION_PORT}"
HEADERS_WITH_USER = {"X-User-ID": USER_ID}
HEADERS_NO_USER = {}

# Non-LLM timeout per case (seconds)
API_TIMEOUT = 5

# LLM endpoint (OpenAI-compatible or judge-provided)
LLM_API_BASE = os.environ.get("LLM_API_BASE", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# Max houses to return
MAX_HOUSES = 5

# History: keep last N turns (2*N messages)
MAX_HISTORY_TURNS = 6
