import logging
from typing import Any, Dict, List, Optional

from . import config
from .api_client import HouseAPI
from .models import SessionState, Slots

logger = logging.getLogger(__name__)

_sessions: Dict[str, SessionState] = {}
_house_api = HouseAPI()
_initialized = False


def ensure_session(session_id: str) -> SessionState:
    global _initialized
    if not _initialized:
        result = _house_api.init_houses()
        logger.info("init_houses result: %s", str(result)[:500])
        _initialized = True
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
