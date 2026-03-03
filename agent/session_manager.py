from typing import Any, Dict, List, Optional

from . import config
from .models import SessionState, Slots

_sessions: Dict[str, SessionState] = {}


def ensure_session(session_id: str) -> SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = SessionState()
    return _sessions[session_id]


def get_session(session_id: str) -> Optional[SessionState]:
    return _sessions.get(session_id)


def append_turn(
    session_id: str,
    user_input: str,
    assistant_message: str,
    *,
    intent: Optional[str] = None,
    slots: Optional[Dict[str, Any]] = None,
    result_house_ids: Optional[List[str]] = None,
) -> None:
    state = _sessions.get(session_id)
    if not state:
        return
    state.history.append({"role": "user", "content": user_input})
    meta = {}
    if intent is not None:
        meta["intent"] = intent
    if slots is not None:
        meta["slots"] = slots
    if result_house_ids is not None:
        meta["result_house_ids"] = result_house_ids
    state.history.append({
        "role": "assistant",
        "content": assistant_message,
        "meta": meta if meta else None,
    })
    # Keep last N turns (2*N messages)
    max_msgs = config.MAX_HISTORY_TURNS * 2
    if len(state.history) > max_msgs:
        state.history = state.history[-max_msgs:]


def set_last_results(session_id: str, results: List[Dict[str, Any]]) -> None:
    state = _sessions.get(session_id)
    if state:
        state.last_results = results


def set_accumulated_filters(session_id: str, slots: Slots) -> None:
    state = _sessions.get(session_id)
    if state:
        state.accumulated_filters = slots


def get_history_for_prompt(session_id: str, max_turns: int = 6) -> List[Dict[str, str]]:
    state = _sessions.get(session_id)
    if not state or not state.history:
        return []
    msgs = state.history[- (max_turns * 2) :]
    return [{"role": m["role"], "content": m["content"]} for m in msgs]


def get_last_result_house_ids(session_id: str) -> List[str]:
    """上一轮返回的房源ID列表，用于指代消解（这套/那套/第一套等）。"""
    state = _sessions.get(session_id)
    if not state or not state.history:
        return []
    for m in reversed(state.history):
        if m.get("role") == "assistant" and isinstance(m.get("meta"), dict):
            ids = m["meta"].get("result_house_ids")
            if ids:
                return ids
    return []
