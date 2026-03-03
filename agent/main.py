"""
Agent entry point: function calling architecture.
LLM decides which tools to call → we execute → LLM generates final response.
"""
import json
import logging
from typing import Any, Dict, List

from . import config
from .api_client import HouseAPI, LandmarkAPI, set_api_user_id, clear_api_user_id
from .llm_client import call_llm, clear_request_llm, set_request_llm
from .tools import TOOLS, SYSTEM_PROMPT
from .session_manager import ensure_session, get_history_for_prompt, get_last_result_house_ids, append_turn

logger = logging.getLogger(__name__)

_house_api = HouseAPI()
_landmark_api = LandmarkAPI()


def handle(session_id: str, user_input: str, model_ip: str = "") -> Dict[str, Any]:
    if model_ip:
        set_request_llm(model_ip, session_id)
    try:
        return _handle_impl(session_id, user_input)
    finally:
        if model_ip:
            clear_request_llm()


def _extract_user_id(session_id: str) -> str:
    """Extract user_id from eval session_id (eval_z00925877_EV-01_xxx -> z00925877)."""
    if session_id.startswith("eval_") and "_EV-" in session_id:
        part = session_id.split("_EV-")[0]
        if part.startswith("eval_"):
            return part[5:]  # after "eval_"
    return config.USER_ID


def _handle_impl(session_id: str, user_input: str) -> Dict[str, Any]:
    user_id = _extract_user_id(session_id)
    set_api_user_id(user_id)
    try:
        return _handle_impl_core(session_id, user_input)
    finally:
        clear_api_user_id()


def _handle_impl_core(session_id: str, user_input: str) -> Dict[str, Any]:
    state = ensure_session(session_id)
    history = get_history_for_prompt(session_id, max_turns=5)
    last_house_ids = get_last_result_house_ids(session_id)

    # Build system prompt with context (last result IDs for 这套/那套 resolution)
    system_content = SYSTEM_PROMPT
    if last_house_ids:
        system_content += f"\n\n【上下文】上一轮返回的房源ID（按顺序）：{', '.join(last_house_ids)}。用户说「这套」「那套」「第一套」「便宜那套」时，用对应ID调用工具。"

    # Build messages: system + history + current user message
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    # Step 1: Call LLM with tools
    result = call_llm(messages, tools=TOOLS, max_tokens=2048, temperature=0.0)
    tool_calls = result.get("tool_calls", [])
    content = result.get("content", "")

    tool_results = []
    house_ids = []

    if tool_calls:
        # Step 2: Execute tool calls
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            tool_result = _execute_tool(tool_name, args)
            tool_results.append({
                "tool": tool_name,
                "params": args,
                "ok": tool_result is not None,
                "result_summary": _summarize_result(tool_result),
            })

            # Add tool result to conversation
            tool_result_str = json.dumps(tool_result, ensure_ascii=False, default=str) if tool_result else '{"error": "工具调用失败"}'
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": tool_name,
                "content": tool_result_str[:3000],
            })

            # Extract house IDs from results
            house_ids.extend(_extract_house_ids_from_result(tool_result))

        # Step 3: Call LLM again with tool results to generate final response
        result2 = call_llm(messages, max_tokens=1024, temperature=0.2)
        content = result2.get("content", "")

        # Handle nested tool calls (LLM might want to call more tools)
        nested_calls = result2.get("tool_calls", [])
        if nested_calls:
            messages.append({"role": "assistant", "content": content, "tool_calls": nested_calls})
            for tc in nested_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_result = _execute_tool(tool_name, args)
                tool_results.append({"tool": tool_name, "params": args, "ok": tool_result is not None})
                tool_result_str = json.dumps(tool_result, ensure_ascii=False, default=str) if tool_result else '{"error": "失败"}'
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": tool_name, "content": tool_result_str[:3000]})
                house_ids.extend(_extract_house_ids_from_result(tool_result))
            result3 = call_llm(messages, max_tokens=1024, temperature=0.2)
            content = result3.get("content", "")

    # Fallback if LLM returned nothing
    if not content:
        content = "没有找到符合条件的房源。请告诉我您的具体需求（区域、户型、预算等），我来帮您查找。"

    # Dedupe house_ids
    seen = set()
    unique_ids = []
    for hid in house_ids:
        if hid and hid not in seen:
            seen.add(hid)
            unique_ids.append(hid)

    append_turn(session_id, user_input, content, result_house_ids=unique_ids)

    return {
        "session_id": session_id,
        "message": content,
        "houses": unique_ids,
        "tool_results": tool_results,
    }


def _normalize_tool_args(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize LLM tool args to avoid ValueError (e.g. max_subway_dist='地铁')."""
    out = dict(args)
    if name == "get_houses_by_platform":
        # max_subway_dist: "地铁"/"近地铁" -> 800, "地铁可达" -> 1000, invalid -> 800
        v = out.get("max_subway_dist")
        if v is not None:
            if isinstance(v, int) and v > 0:
                pass
            elif isinstance(v, str):
                s = str(v).strip()
                if "可达" in s or s == "1000":
                    out["max_subway_dist"] = 1000
                elif "近" in s or "地铁" in s or s == "800" or not s.isdigit():
                    out["max_subway_dist"] = 800
                else:
                    try:
                        out["max_subway_dist"] = int(float(s))
                    except (ValueError, TypeError):
                        out["max_subway_dist"] = 800
            else:
                try:
                    out["max_subway_dist"] = int(v)
                except (ValueError, TypeError):
                    out["max_subway_dist"] = 800
        # Coerce numeric params; invalid -> None (omit from API)
        for key in ("min_price", "max_price", "min_area", "max_area", "commute_to_xierqi_max"):
            v = out.get(key)
            if v is None:
                continue
            try:
                out[key] = int(float(v)) if v != "" else None
            except (ValueError, TypeError):
                out[key] = None
        # elevator: bool or "true"/"false" string
        ev = out.get("elevator")
        if ev is not None and isinstance(ev, str) and ev.lower() not in ("true", "false"):
            out["elevator"] = None
        # sort_by: subway -> subway_distance
        sb = out.get("sort_by")
        if sb and isinstance(sb, str) and sb.lower() in ("subway", "subway_dist"):
            out["sort_by"] = "subway_distance"
        # 默认多取一些结果供筛选
        if out.get("page_size") is None:
            out["page_size"] = 50
    return out


def _execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute a tool call against the simulation API."""
    try:
        args = _normalize_tool_args(name, args)
        if name == "get_houses_by_platform":
            return _house_api.get_houses_by_platform(**args)
        if name == "get_house_by_id":
            return _house_api.get_house(args.get("house_id", ""))
        if name == "get_house_listings":
            return _house_api.get_house_listings(args.get("house_id", ""))
        if name == "get_houses_nearby":
            return _house_api.get_houses_nearby(
                landmark_id=args.get("landmark_id", ""),
                max_distance=args.get("max_distance", 2000),
                listing_platform=args.get("listing_platform"),
            )
        if name == "get_houses_by_community":
            return _house_api.get_houses_by_community(
                community=args.get("community", ""),
                listing_platform=args.get("listing_platform"),
            )
        if name == "rent_house":
            ok, result = _house_api.rent_house(
                house_id=args.get("house_id", ""),
                listing_platform=args.get("listing_platform", "安居客"),
            )
            return result if ok else {"error": "租房失败", "detail": str(result)}
        if name == "terminate_rental":
            ok, result = _house_api.terminate_house(
                house_id=args.get("house_id", ""),
                listing_platform=args.get("listing_platform", "安居客"),
            )
            return result if ok else {"error": "退租失败", "detail": str(result)}
        if name == "get_landmarks":
            return _landmark_api.get_landmarks(
                category=args.get("category"),
                district=args.get("district"),
            )
        if name == "get_nearby_landmarks":
            return _house_api.get_nearby_landmarks(
                community=args.get("community", ""),
                type_=args.get("type"),
            )
        logger.warning("Unknown tool: %s", name)
        return None
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        return {"error": str(e)}


def _extract_house_ids_from_result(result: Any) -> List[str]:
    """Extract house_id values from API results."""
    ids = []
    if not result:
        return ids
    if isinstance(result, dict):
        if "house_id" in result:
            ids.append(result["house_id"])
        if "id" in result and str(result["id"]).startswith("HF"):
            ids.append(result["id"])
        if "items" in result:
            for item in (result["items"] or []):
                hid = item.get("house_id") or item.get("id")
                if hid:
                    ids.append(str(hid))
        if "data" in result and isinstance(result["data"], dict):
            hid = result["data"].get("house_id") or result["data"].get("id")
            if hid:
                ids.append(str(hid))
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                hid = item.get("house_id") or item.get("id")
                if hid:
                    ids.append(str(hid))
    return ids


def _summarize_result(result: Any) -> str:
    if result is None:
        return "failed"
    if isinstance(result, dict):
        if "items" in result:
            return f"total={result.get('total', 0)}"
        if "error" in result:
            return f"error: {result['error']}"
        if "house_id" in result:
            return f"house={result['house_id']}"
    return "ok"


def run_app():
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
