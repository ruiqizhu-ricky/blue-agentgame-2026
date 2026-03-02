"""
Entry point: receive judge request (session_id, user_input), return { session_id, message, houses }.
"""
from typing import Any, Dict, List

from . import config
from .api_executor import execute_calls
from .api_planner import plan_calls, resolve_reference, slots_to_by_platform_params
from .intent_parser import merge_slots, parse_intent
from .llm_client import clear_request_llm, set_request_llm
from .models import Intent, Slots
from .post_processor import process as post_process
from .response_generator import generate_reply
from .session_manager import (
    ensure_session,
    get_history_for_prompt,
    get_session,
    set_accumulated_filters,
    set_last_results,
    append_turn,
)


def _extract_house_ids(houses: List[Dict[str, Any]]) -> List[str]:
    ids = []
    for h in houses:
        hid = h.get("house_id") or h.get("id")
        if hid:
            ids.append(str(hid))
    return ids


def _no_match_from_tool_results(
    tool_results: List[Dict[str, Any]],
    house_results: List[Dict[str, Any]],
    total: int,
) -> bool:
    """根据工具调用结果与聚合结果判断无匹配：总数为0且无房源；或主查询工具失败/返回0条。"""
    if total == 0 and not house_results:
        return True
    # 若主查询工具（唯一或第一个）明确返回 0 或失败，以工具为准
    for t in tool_results:
        if not t.get("ok"):
            return True
        name = t.get("tool", "")
        if name in ("get_houses_by_platform", "get_houses_by_community", "get_houses_nearby"):
            if t.get("total", 0) == 0 and t.get("items_count", 0) == 0:
                return True
            break
        if name == "get_house":
            if not t.get("house_id"):
                return True
            break
    return False


def _rent_ok_from_tool_results(tool_results: List[Dict[str, Any]]) -> bool:
    """根据工具调用结果判断租赁是否成功。"""
    for t in tool_results:
        if t.get("tool") == "rent_house" and t.get("ok"):
            return True
    return False


def handle(session_id: str, user_input: str, model_ip: str = "") -> Dict[str, Any]:
    """Process one user turn; return { session_id, message, houses }.
    When model_ip is set (from contest /api/v1/chat), LLM is called at http://model_ip:8888 with Session-ID.
    """
    if model_ip:
        set_request_llm(model_ip, session_id)
    try:
        return _handle_impl(session_id, user_input)
    finally:
        if model_ip:
            clear_request_llm()


def _handle_impl(session_id: str, user_input: str) -> Dict[str, Any]:
    state = ensure_session(session_id)
    # 仅取最近 3 轮供 prompt，省 token
    history = get_history_for_prompt(session_id, max_turns=3)
    last_result_ids = _extract_house_ids(state.last_results)

    intent, slots, ref_to_last, ref_index = parse_intent(user_input, history, last_result_ids)

    # Merge slots for FOLLOW_UP
    if intent == Intent.FOLLOW_UP and state.accumulated_filters is not None:
        slots = merge_slots(state.accumulated_filters, slots)
    elif intent == Intent.QUERY_HOUSE or intent == Intent.FOLLOW_UP:
        state.accumulated_filters = slots

    # Resolve house_id for rent/terminate/offline from last_results
    if intent in (Intent.RENT_HOUSE, Intent.TERMINATE_LEASE, Intent.OFFLINE_HOUSE) and not slots.house_id:
        house_id = resolve_reference(user_input, state.last_results, ref_index)
        if house_id:
            slots = Slots(house_id=house_id, listing_platform=slots.listing_platform or "安居客")

    # CHAT: no API, generate reply only
    if intent == Intent.CHAT:
        message = generate_reply(user_input, Slots(), [], 0, history, intent="chat")
        append_turn(session_id, user_input, message, intent=intent.value, result_house_ids=[])
        return {"session_id": session_id, "message": message, "houses": [], "tool_results": []}

    calls = plan_calls(intent, slots)
    house_results, extra, tool_results = execute_calls(calls) if calls else ([], {}, [])

    # Sort params for post_process (from slots)
    sort_by = slots.sort_by
    sort_order = slots.sort_order
    if not sort_by and intent == Intent.QUERY_HOUSE and slots.max_subway_dist:
        sort_by = "subway_distance"
        sort_order = sort_order or "asc"

    processed, total = post_process(
        house_results,
        slots,
        sort_by=sort_by,
        sort_order=sort_order,
        max_houses=config.MAX_HOUSES,
    )

    set_last_results(session_id, processed)
    if intent == Intent.FOLLOW_UP:
        set_accumulated_filters(session_id, slots)

    # 用工具调用结果做判断：无结果 / 租赁成功 以 tool_results 为准
    no_match = _no_match_from_tool_results(tool_results, house_results, total)
    rent_ok = intent == Intent.RENT_HOUSE and slots.house_id and _rent_ok_from_tool_results(tool_results)
    ask_more = "其他" in user_input or "都给" in user_input
    single_match_phrase = total == 1 and ask_more and intent == Intent.FOLLOW_UP

    message = generate_reply(
        user_input,
        slots,
        processed,
        total,
        history,
        intent=intent.value,
        no_match=no_match,
        single_match=single_match_phrase,
        rent_ok=rent_ok,
        listings=extra.get("listings"),
        tool_results=tool_results,
    )

    house_ids = _extract_house_ids(processed)
    if intent == Intent.RENT_HOUSE and slots.house_id and slots.house_id not in house_ids:
        house_ids = [slots.house_id]

    append_turn(
        session_id,
        user_input,
        message,
        intent=intent.value,
        slots=slots.to_dict(),
        result_house_ids=house_ids,
    )

    return {"session_id": session_id, "message": message, "houses": house_ids, "tool_results": tool_results}


def run_app():
    """Simple HTTP server or CLI for testing."""
    import json
    import sys
    if len(sys.argv) >= 3:
        session_id = sys.argv[1]
        user_input = sys.argv[2]
        out = handle(session_id, user_input)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("Usage: python -m agent.main <session_id> <user_input>", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_app()
