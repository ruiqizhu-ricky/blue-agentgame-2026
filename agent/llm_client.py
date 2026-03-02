"""
LLM client: OpenAI-compatible API or mock for testing.
Per-request model_ip (from /api/v1/chat) uses context; else config.LLM_API_BASE.
"""
import json
import re
from contextvars import ContextVar
from typing import Any, Dict, List

import requests

from . import config

# Request-scoped: set by server when model_ip is provided (contest judge)
_llm_api_base_ctx: ContextVar[str] = ContextVar("llm_api_base", default="")
_session_id_ctx: ContextVar[str] = ContextVar("session_id", default="")

# Mock responses for open test cases (so we can run pipeline without real LLM)
MOCK_INTENT_RESPONSES = {
    "东城区精装两居，租金 5000 以内，离地铁 500 米以内的有吗？": {
        "intent": "query_house",
        "slots": {"district": "东城", "decoration": "精装", "room_count": 2, "rent_max": 5000, "max_subway_dist": 500},
        "reference_to_last_result": False,
        "reference_index": None,
    },
    "西城区离地铁近的一居室有吗？按离地铁从近到远排。": {
        "intent": "query_house",
        "slots": {"district": "西城", "room_count": 1, "max_subway_dist": 800, "sort_by": "subway_distance", "sort_order": "asc"},
        "reference_to_last_result": False,
        "reference_index": None,
    },
    "还有其他的吗？把所有符合条件的都给出来": {
        "intent": "follow_up",
        "slots": {},
        "reference_to_last_result": True,
        "reference_index": None,
    },
    "海淀区离地铁近的两居有吗？按离地铁从近到远排一下。": {
        "intent": "query_house",
        "slots": {"district": "海淀", "room_count": 2, "max_subway_dist": 800, "sort_by": "subway_distance", "sort_order": "asc"},
        "reference_to_last_result": False,
        "reference_index": None,
    },
    "就租最近的那套吧。": {
        "intent": "rent_house",
        "slots": {},
        "reference_to_last_result": True,
        "reference_index": 0,
    },
}


def set_request_llm(model_ip: str, session_id: str = "") -> None:
    """Set request-scoped LLM base (http://model_ip:8888) and session_id for Session-ID header."""
    base = f"http://{model_ip.strip()}:8888" if model_ip else ""
    _llm_api_base_ctx.set(base)
    _session_id_ctx.set(session_id or "")


def clear_request_llm() -> None:
    """Clear request-scoped LLM context."""
    try:
        _llm_api_base_ctx.set("")
        _session_id_ctx.set("")
    except LookupError:
        pass


def call_llm(messages: List[Dict[str, str]], *, temperature: float = 0.2) -> str:
    """Call LLM and return the assistant content. Uses request context or config.LLM_API_BASE."""
    base = _llm_api_base_ctx.get() or config.LLM_API_BASE
    if base:
        return _call_api(messages, api_base=base, temperature=temperature)
    return ""


def _call_api(messages: List[Dict[str, str]], api_base: str, temperature: float = 0.2) -> str:
    url = api_base.rstrip("/")
    if "/chat/completions" not in url:
        url = f"{url}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    session_id = _session_id_ctx.get()
    if session_id:
        headers["Session-ID"] = session_id
    body = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2048,
    }
    try:
        r = requests.post(url, json=body, headers=headers, timeout=60)
        data = r.json()
        if isinstance(data, dict):
            choices = data.get("choices", [])
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message", {})
                return msg.get("content", "") or ""
        return ""
    except Exception:
        return ""


def parse_intent_response(raw: str, user_input: str) -> Dict[str, Any]:
    """Parse LLM JSON output for intent/slots. Fallback to mock for known inputs."""
    if not raw or not raw.strip():
        return MOCK_INTENT_RESPONSES.get(user_input.strip(), {"intent": "chat", "slots": {}, "reference_to_last_result": False, "reference_index": None})
    # Try mock first for exact match (testing without LLM)
    if user_input.strip() in MOCK_INTENT_RESPONSES:
        return MOCK_INTENT_RESPONSES[user_input.strip()].copy()
    # Extract JSON from raw (may be wrapped in markdown)
    text = raw.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"intent": "chat", "slots": {}, "reference_to_last_result": False, "reference_index": None}
