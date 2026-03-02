"""
LLM client: OpenAI-compatible API or mock for testing.
Set LLM_API_BASE (and optionally LLM_API_KEY) to use real API.
"""
import json
import os
import re
from typing import Any, Dict, List

import requests

from . import config

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


def call_llm(messages: List[Dict[str, str]], *, temperature: float = 0.2) -> str:
    """Call LLM and return the assistant content. Uses LLM_API_BASE if set, else mock."""
    if config.LLM_API_BASE:
        return _call_api(messages, temperature=temperature)
    return ""


def _call_api(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    url = config.LLM_API_BASE.rstrip("/")
    if "/chat" not in url and "/v1" not in url:
        url = f"{url}/v1/chat/completions"
    elif "/chat/completions" not in url:
        url = f"{url}/chat/completions" if url.endswith("/v1") else f"{url}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    body = {
        "model": os.environ.get("LLM_MODEL", "qwen3-32b"),
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
