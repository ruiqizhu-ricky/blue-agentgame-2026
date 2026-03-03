"""
LLM client: OpenAI-compatible API or mock for testing.
Per-request model_ip (from /api/v1/chat) uses context; else config.LLM_API_BASE.
"""
import json
import logging
import re
import time
from contextvars import ContextVar
from typing import Any, Dict, List

import requests

from . import config

logger = logging.getLogger(__name__)

_llm_api_base_ctx: ContextVar[str] = ContextVar("llm_api_base", default="")
_session_id_ctx: ContextVar[str] = ContextVar("session_id", default="")

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
    base = f"http://{model_ip.strip()}:8888" if model_ip else ""
    _llm_api_base_ctx.set(base)
    _session_id_ctx.set(session_id or "")


def clear_request_llm() -> None:
    try:
        _llm_api_base_ctx.set("")
        _session_id_ctx.set("")
    except LookupError:
        pass


MAX_RETRIES = 2
RETRY_DELAY = 1.0


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from qwen3 output."""
    if not text or "<think>" not in text:
        return text
    return re.sub(r"<think>[\s\S]*?</think>\s*", "", text).strip()


def call_llm(messages: List[Dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 1024) -> str:
    """Call LLM with retry. Returns "" only when all retries exhausted."""
    base = _llm_api_base_ctx.get() or config.LLM_API_BASE
    if not base:
        logger.error("LLM base URL is empty! ContextVar=%r, config=%r", _llm_api_base_ctx.get(), config.LLM_API_BASE)
        return ""
    for attempt in range(MAX_RETRIES + 1):
        result = _call_api(messages, api_base=base, temperature=temperature, max_tokens=max_tokens)
        if result:
            return result
        if attempt < MAX_RETRIES:
            logger.warning("LLM returned empty (attempt %d/%d), retrying in %.1fs...", attempt + 1, MAX_RETRIES + 1, RETRY_DELAY)
            time.sleep(RETRY_DELAY)
    logger.error("LLM returned empty after %d attempts", MAX_RETRIES + 1)
    return ""


def _call_api(messages: List[Dict[str, str]], api_base: str, temperature: float = 0.2, max_tokens: int = 1024) -> str:
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
        "max_tokens": max_tokens,
        "enable_thinking": False,
    }
    try:
        r = requests.post(url, json=body, headers=headers, timeout=60)
        if r.status_code != 200:
            logger.error("LLM HTTP %d: %s", r.status_code, r.text[:300])
            return ""
        data = r.json()
        if isinstance(data, dict):
            choices = data.get("choices", [])
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message", {})
                content = msg.get("content") or ""
                if not content:
                    content = msg.get("reasoning_content") or ""
                if not content:
                    logger.warning("LLM message fields: %s", list(msg.keys()))
                # Strip <think>...</think> tags that qwen3 might include
                content = _strip_think_tags(content)
                return content
        logger.warning("LLM unexpected response format: %s", str(data)[:300])
        return ""
    except requests.Timeout:
        logger.error("LLM timeout (60s)")
        return ""
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return ""


def parse_intent_response(raw: str, user_input: str) -> Dict[str, Any]:
    """Parse LLM JSON output. Fallback to rule-based when LLM unavailable."""
    if not raw or not raw.strip():
        mock = MOCK_INTENT_RESPONSES.get(user_input.strip())
        if mock:
            return mock
        return _rule_based_intent(user_input)
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
        return _rule_based_intent(user_input)


# ---- Rule-based fallback when LLM is unavailable ----

_DISTRICT_KEYWORDS = {
    "海淀": ("海淀", None), "朝阳": ("朝阳", None), "大兴": ("大兴", None), "通州": ("通州", None),
    "昌平": ("昌平", None), "房山": ("房山", None), "西城": ("西城", None), "丰台": ("丰台", None),
    "顺义": ("顺义", None), "东城": ("东城", None),
    "望京": (None, "望京"), "国贸": (None, "国贸"), "西二旗": (None, "西二旗"),
    "中关村": (None, "中关村"), "上地": (None, "上地"), "五道口": (None, "五道口"),
    "酒仙桥": (None, "酒仙桥"), "三里屯": (None, "三里屯"), "亚运村": (None, "亚运村"),
    "回龙观": (None, "回龙观"), "天通苑": (None, "天通苑"),
}
_ROOM_PATTERNS = [
    (re.compile(r"一居|1居|一室"), 1),
    (re.compile(r"两居|2居|二居|二室|两室"), 2),
    (re.compile(r"三居|3居|三室"), 3),
]
_PRICE_MAX_RE = re.compile(r"(\d{3,5})\s*(?:元|块)?(?:以内|以下|以里|之内|之下|左右)?")
_HF_RE = re.compile(r"HF[_\-]?\d+", re.IGNORECASE)


def _rule_based_intent(user_input: str) -> Dict[str, Any]:
    """No LLM available: extract intent/slots from text with rules."""
    text = user_input.strip()

    # Greeting
    if text in ("你好", "您好", "嗨") or text.startswith("你好") and len(text) <= 10:
        return {"intent": "chat", "slots": {}}
    if "可以做什么" in text or "能做什么" in text:
        return {"intent": "chat", "slots": {}}

    # Rent
    hf_match = _HF_RE.search(text)
    house_id = hf_match.group().replace("-", "_").upper() if hf_match else None

    if house_id and ("租" in text or "办理" in text or "预约" in text):
        return {"intent": "rent_house", "slots": {"house_id": house_id}, "reference_to_last_result": False, "reference_index": None}
    if ("就租" in text or "我要租" in text or "帮我租" in text) and not house_id:
        if "第一" in text or "第1" in text:
            return {"intent": "rent_house", "slots": {}, "reference_to_last_result": True, "reference_index": 0}
        if "第二" in text or "第2" in text:
            return {"intent": "rent_house", "slots": {}, "reference_to_last_result": True, "reference_index": 1}
        return {"intent": "rent_house", "slots": {}, "reference_to_last_result": True, "reference_index": 0}

    # Terminate
    if "退租" in text or "退掉" in text or "不租了" in text:
        return {"intent": "terminate_lease", "slots": {"house_id": house_id or ""}, "reference_to_last_result": not bool(house_id), "reference_index": 0}

    # Compare (ask about specific house)
    if house_id and ("详细" in text or "情况" in text or "电梯" in text or "朝向" in text or "面积" in text or "平台" in text or "价格" in text or "多少钱" in text or "地铁" in text or "采光" in text or "噪音" in text or "入住" in text):
        return {"intent": "compare_houses", "slots": {"house_id": house_id}, "reference_to_last_result": False, "reference_index": None}

    # Query house: build slots from text
    slots: Dict[str, Any] = {}
    for kw, (dist, biz_area) in _DISTRICT_KEYWORDS.items():
        if kw in text:
            if dist:
                slots["district"] = dist
            if biz_area:
                slots["business_area"] = biz_area
            break
    for pat, count in _ROOM_PATTERNS:
        if pat.search(text):
            slots["room_count"] = count
            break
    prices = _PRICE_MAX_RE.findall(text)
    if prices:
        vals = [int(p) for p in prices]
        if len(vals) >= 2:
            slots["rent_min"] = min(vals)
            slots["rent_max"] = max(vals)
        else:
            slots["rent_max"] = vals[0]
    if "精装" in text:
        slots["decoration"] = "精装"
    if "简装" in text:
        slots["decoration"] = "简装"
    if "电梯" in text:
        slots["has_elevator"] = True
    if "近地铁" in text or "地铁近" in text:
        slots["max_subway_dist"] = 800
        slots["near_subway"] = True
    subway_line_m = re.search(r"(\d{1,2}号线)", text)
    if subway_line_m:
        slots["subway_line"] = subway_line_m.group(1)
    station_m = re.search(r"([\u4e00-\u9fff]{2,6}站)", text)
    if station_m and "地铁站" not in station_m.group():
        slots["subway_station"] = station_m.group(1)
    if "民水民电" in text:
        slots["utilities_type"] = "民水民电"
    if "商水商电" in text:
        slots["utilities_type"] = "商水商电"
    if "整租" in text:
        slots["rental_type"] = "整租"
    if "合租" in text:
        slots["rental_type"] = "合租"
    if "链家" in text:
        slots["listing_platform"] = "链家"
    elif "安居客" in text:
        slots["listing_platform"] = "安居客"
    elif "58同城" in text:
        slots["listing_platform"] = "58同城"
    if house_id:
        slots["house_id"] = house_id

    # Determine intent
    if house_id and not slots.get("district") and not slots.get("room_count"):
        intent = "compare_houses"
    elif "找" in text or "查" in text or "看看" in text or "推荐" in text or "有哪些" in text or "有没有" in text or "有吗" in text or slots.get("district") or slots.get("room_count") or slots.get("rent_max"):
        intent = "query_house"
    elif "这套" in text or "第一套" in text or "便宜" in text:
        intent = "follow_up"
        return {"intent": intent, "slots": slots, "reference_to_last_result": True, "reference_index": 0}
    else:
        intent = "chat"

    return {"intent": intent, "slots": slots, "reference_to_last_result": False, "reference_index": None}
