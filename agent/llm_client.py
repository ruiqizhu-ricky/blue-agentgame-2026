"""
LLM client with function calling (tool use) support for qwen3.
"""
import json
import logging
import re
import time
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

import requests

from . import config

logger = logging.getLogger(__name__)

_llm_api_base_ctx: ContextVar[str] = ContextVar("llm_api_base", default="")
_session_id_ctx: ContextVar[str] = ContextVar("session_id", default="")


def set_request_llm(model_ip: str, session_id: str = "") -> None:
    base = f"http://{model_ip.strip()}:8888" if model_ip else ""
    _llm_api_base_ctx.set(base)
    _session_id_ctx.set(session_id or "")


def clear_request_llm() -> None:
    try:
        _llm_api_base_ctx.set("")
        _session_id_ctx.set("")
    except LookupError:
        pass


def _strip_think_tags(text: str) -> str:
    if not text or "<think>" not in text:
        return text
    return re.sub(r"<think>[\s\S]*?</think>\s*", "", text).strip()


MAX_RETRIES = 1
RETRY_DELAY = 0.5


def call_llm(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    tools: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Call LLM. Returns {"content": str, "tool_calls": list} dict."""
    base = _llm_api_base_ctx.get() or config.LLM_API_BASE
    if not base:
        logger.error("LLM base URL is empty")
        return {"content": "", "tool_calls": []}
    for attempt in range(MAX_RETRIES + 1):
        result = _call_api(messages, api_base=base, temperature=temperature, max_tokens=max_tokens, tools=tools)
        if result.get("content") or result.get("tool_calls"):
            return result
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    return {"content": "", "tool_calls": []}


def call_llm_text(messages: List[Dict[str, Any]], *, temperature: float = 0.2, max_tokens: int = 1024) -> str:
    """Simple text-only call (no tools). Returns content string."""
    result = call_llm(messages, temperature=temperature, max_tokens=max_tokens)
    return result.get("content", "")


def _call_api(
    messages: List[Dict[str, Any]],
    api_base: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    tools: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    url = api_base.rstrip("/")
    if "/chat/completions" not in url:
        url = f"{url}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    session_id = _session_id_ctx.get()
    if session_id:
        headers["Session-ID"] = session_id
    body: Dict[str, Any] = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "enable_thinking": False,
    }
    if tools:
        body["tools"] = tools
    try:
        r = requests.post(url, json=body, headers=headers, timeout=60)
        if r.status_code != 200:
            logger.error("LLM HTTP %d: %s", r.status_code, r.text[:300])
            return {"content": "", "tool_calls": []}
        data = r.json()
        if isinstance(data, dict):
            choices = data.get("choices", [])
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message", {})
                content = _strip_think_tags(msg.get("content") or "")
                tool_calls = msg.get("tool_calls") or []
                return {"content": content, "tool_calls": tool_calls}
        logger.warning("LLM unexpected response: %s", str(data)[:300])
        return {"content": "", "tool_calls": []}
    except requests.Timeout:
        logger.error("LLM timeout")
        return {"content": "", "tool_calls": []}
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return {"content": "", "tool_calls": []}
