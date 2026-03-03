"""
Entry point: receive judge request (session_id, user_input), return { session_id, message, houses }.
"""
import logging
from typing import Any, Dict, List, Optional

from . import config
from .api_executor import execute_calls
from .api_planner import plan_calls, resolve_reference, slots_to_by_platform_params
from .intent_parser import merge_slots, parse_intent
from .api_client import set_api_user_id, clear_api_user_id
from .house_cache import ensure_cache, search_houses as cache_search
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

logger = logging.getLogger(__name__)


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
    if total == 0 and not house_results:
        return True
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
    for t in tool_results:
        if t.get("tool") == "rent_house" and t.get("ok"):
            return True
    return False


def _slots_to_cache_params(slots: Slots) -> dict:
    """Convert Slots to cache_search kwargs."""
    p = {}
    if slots.district:
        p["district"] = slots.district
    if slots.business_area:
        p["business_area"] = slots.business_area
    if slots.room_counts:
        p["bedrooms"] = slots.room_counts
    elif slots.room_count is not None:
        p["bedrooms"] = str(slots.room_count)
    if slots.rent_min is not None:
        p["min_price"] = int(slots.rent_min)
    if slots.rent_max is not None:
        p["max_price"] = int(slots.rent_max)
    if slots.area_min is not None:
        p["min_area"] = int(slots.area_min)
    if slots.area_max is not None:
        p["max_area"] = int(slots.area_max)
    if slots.decoration:
        p["decoration"] = slots.decoration
    if slots.orientation:
        p["orientation"] = slots.orientation
    if slots.has_elevator is not None:
        p["elevator"] = "true" if slots.has_elevator else "false"
    if slots.max_subway_dist is not None:
        p["max_subway_dist"] = slots.max_subway_dist
    if slots.subway_line:
        p["subway_line"] = slots.subway_line
    if slots.subway_station:
        p["subway_station"] = slots.subway_station
    if slots.utilities_type:
        p["utilities_type"] = slots.utilities_type
    if slots.rental_type:
        p["rental_type"] = slots.rental_type
    if slots.listing_platform:
        p["listing_platform"] = slots.listing_platform
    if slots.max_commute_time is not None:
        p["commute_to_xierqi_max"] = slots.max_commute_time
    if slots.move_in_date:
        p["available_from_before"] = slots.move_in_date
    if slots.sort_by:
        p["sort_by"] = {"rent_price": "price", "subway_distance": "subway", "area": "area"}.get(slots.sort_by, slots.sort_by)
    if slots.sort_order:
        p["sort_order"] = slots.sort_order
    return p


def _broaden_slots(slots: Slots) -> Optional[Slots]:
    """Remove the most restrictive filter to broaden the search. Returns None if nothing to remove."""
    import copy
    s = copy.deepcopy(slots)
    # Priority: remove decoration → elevator → subway_dist → area → orientation → utilities
    if s.decoration:
        s.decoration = None
        return s
    if s.has_elevator is not None:
        s.has_elevator = None
        return s
    if s.max_subway_dist is not None:
        s.max_subway_dist = None
        s.near_subway = None
        return s
    if s.area_min is not None:
        s.area_min = None
        return s
    if s.orientation:
        s.orientation = None
        return s
    if s.utilities_type:
        s.utilities_type = None
        return s
    if s.subway_line:
        s.subway_line = None
        return s
    if s.subway_station:
        s.subway_station = None
        return s
    return None


def _extract_user_id(session_id: str) -> str:
    if session_id.startswith("eval_"):
        parts = session_id.split("_")
        if len(parts) >= 2:
            return parts[1]
    return ""


def handle(session_id: str, user_input: str, model_ip: str = "") -> Dict[str, Any]:
    if model_ip:
        set_request_llm(model_ip, session_id)
    user_id = _extract_user_id(session_id)
    if user_id:
        set_api_user_id(user_id)
    try:
        return _handle_impl(session_id, user_input)
    finally:
        if model_ip:
            clear_request_llm()
        if user_id:
            clear_api_user_id()


def _handle_impl(session_id: str, user_input: str) -> Dict[str, Any]:
    state = ensure_session(session_id)
    history = get_history_for_prompt(session_id, max_turns=3)
    last_result_ids = _extract_house_ids(state.last_results)

    intent, slots, ref_to_last, ref_index = parse_intent(user_input, history, last_result_ids)

    # Merge slots for FOLLOW_UP
    if intent == Intent.FOLLOW_UP and state.accumulated_filters is not None:
        slots = merge_slots(state.accumulated_filters, slots)
    elif intent == Intent.QUERY_HOUSE:
        state.accumulated_filters = slots

    # Resolve house_id for rent/terminate/offline from last_results
    if intent in (Intent.RENT_HOUSE, Intent.TERMINATE_LEASE, Intent.OFFLINE_HOUSE) and not slots.house_id:
        house_id = resolve_reference(user_input, state.last_results, ref_index)
        if house_id:
            slots = Slots(house_id=house_id, listing_platform=slots.listing_platform or "安居客")

    # CHAT: no API
    if intent == Intent.CHAT:
        message = generate_reply(user_input, Slots(), [], 0, history, intent="chat")
        append_turn(session_id, user_input, message, intent=intent.value, result_house_ids=[])
        return {"session_id": session_id, "message": message, "houses": [], "tool_results": []}

    # Ensure cache is loaded
    ensure_cache()

    calls = plan_calls(intent, slots)
    house_results, extra, tool_results = execute_calls(calls) if calls else ([], {}, [])

    # ---- Cache fallback: if API returns 0 for query, try client-side search ----
    if intent in (Intent.QUERY_HOUSE, Intent.FOLLOW_UP) and not house_results and not slots.house_id:
        cache_params = _slots_to_cache_params(slots)
        cache_result = cache_search(**cache_params)
        if cache_result.get("items"):
            house_results = cache_result["items"]
            logger.info("Cache fallback found %d results", len(house_results))
            tool_results.append({"tool": "cache_search", "params": cache_params, "ok": True, "total": cache_result["total"], "items_count": len(house_results)})

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
    if intent in (Intent.QUERY_HOUSE, Intent.FOLLOW_UP):
        set_accumulated_filters(session_id, slots)

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
