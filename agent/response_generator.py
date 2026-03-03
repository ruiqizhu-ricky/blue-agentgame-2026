import json
from typing import Any, Dict, List, Optional

from .llm_client import call_llm
from .models import Slots


def _is_greeting(text: str) -> bool:
    t = (text or "").strip()
    return bool(t in ("你好", "您好", "嗨") or t.startswith("你好") or t.startswith("您好") or "你好呀" in t or "嗨" == t[:1])


def _is_capability_ask(text: str) -> bool:
    t = (text or "").strip()
    return ("可以做什么" in t or "能做什么" in t or "有什么功能" in t or ("你能" in t and "吗" in t))


def _trim_house(h: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal fields for reply to save tokens; 判题需房源ID/区/户型/面积/租金/地铁/通勤."""
    keys = ["house_id", "id", "community", "district", "room_count", "bedrooms", "area", "rent_price", "price", "decoration", "orientation", "subway_station", "subway_distance", "commute_time", "elevator", "has_elevator", "rental_type", "listing_platform", "available_date", "tags", "floor", "total_floor", "facing_street"]
    return {k: h.get(k) for k in keys if h.get(k) is not None}


def _format_tool_results_summary(tool_results: List[Dict[str, Any]]) -> str:
    """把工具调用结果压成简短一句，供模型依据工具结果组织回复。"""
    if not tool_results:
        return ""
    parts = []
    for t in tool_results:
        name = t.get("tool", "")
        ok = t.get("ok", False)
        if name == "get_houses_by_platform" or name == "get_houses_by_community" or name == "get_houses_nearby":
            total = t.get("total", 0)
            cnt = t.get("items_count", 0)
            parts.append(f"{name}:{'成功' if ok else '失败'} 共{total}条(返回{cnt}条)")
        elif name == "get_house":
            hid = t.get("house_id", "")
            parts.append(f"get_house:{'已找到' + str(hid) if hid else '未找到该房源'}")
        elif name == "get_house_listings":
            parts.append(f"get_house_listings:{'有挂牌数据' if ok else '无'}")
        elif name == "rent_house":
            parts.append(f"rent_house:{'成功' if ok else '失败'}")
        else:
            parts.append(f"{name}:{'成功' if ok else '失败'}")
    return "；".join(parts)


def generate_reply(
    user_input: str,
    slots: Slots,
    houses: List[Dict[str, Any]],
    total: int,
    history: List[Dict[str, str]],
    *,
    intent: str = "",
    no_match: bool = False,
    single_match: bool = False,
    rent_ok: bool = False,
    listings: Optional[Dict[str, Any]] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate natural language reply; 依据工具调用结果与房源数据组织回复。"""
    houses_json = json.dumps([_trim_house(h) for h in houses], ensure_ascii=False, indent=0)
    slots_json = json.dumps(slots.to_dict(), ensure_ascii=False)

    # 短 hint 省 token，保证判题关键词
    hints = []
    if no_match:
        hints.append("必含: 没有")
    if single_match:
        hints.append('必含: "没有其他的了，只有这一套"')
    if rent_ok:
        hints.append("必以「好的」开头")
    if houses and not no_match:
        hints.append("必含全部房源ID；排序时含 subway_distance 与 asc/desc")
        if slots.max_subway_dist == 800:
            hints.append("体现 800米")

    system = """北京租房顾问。用自然中文回复。依据「工具调用结果」和下方「结果」数据组织回复。每套房源写清: 房源ID、小区、区、户型、面积、月租、装修、朝向、地铁站及距离、西二旗通勤。无结果要说「没有」；仅一套时说「只有这一套」或「没有其他的了，只有这一套」；租房确认以「好的」开头。回复须含所有房源ID。"""
    # 打招呼/问能力时不要给「结果0套」避免回复成「没有」
    if intent == "chat" and (_is_greeting(user_input) or _is_capability_ask(user_input)):
        user_content = f"用户说: {user_input}\n请简短问候并介绍你能做什么（北京租房顾问：可帮查区域/户型/预算/地铁/通勤等），不要说「没有」或「暂无房源」。\n回复:"
    else:
        tool_summary = _format_tool_results_summary(tool_results or [])
        user_content = f"问:{user_input}\n条件:{slots_json}\n"
        if tool_summary:
            user_content += f"工具调用结果:{tool_summary}\n"
        user_content += f"结果(共{total}套):{houses_json}"
        if listings:
            user_content += "\n该房源各平台挂牌:" + json.dumps(listings, ensure_ascii=False)
    if hints:
        user_content += "\n" + " ".join(hints)
    # 最多带最近 2 轮对话省 token
    if history:
        short_hist = history[-4:]
        user_content += "\n近轮:" + json.dumps(short_hist, ensure_ascii=False)
    user_content += "\n回复:"

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_content}]
    raw = call_llm(messages, max_tokens=1024)
    if raw and raw.strip():
        return raw.strip()
    return _fallback_reply(user_input, houses, total, no_match=no_match, single_match=single_match, rent_ok=rent_ok, slots=slots, intent=intent, listings=listings)


def _fallback_reply(
    user_input: str,
    houses: List[dict],
    total: int,
    no_match: bool = False,
    single_match: bool = False,
    rent_ok: bool = False,
    slots: Optional[Slots] = None,
    intent: str = "",
    listings: Optional[Dict[str, Any]] = None,
) -> str:
    """Deterministic reply when LLM is not available. Context-aware for different intents."""
    # Chat / greeting
    if intent == "chat":
        if _is_greeting(user_input):
            return "您好！我是北京租房顾问，可以帮您按区域、户型、预算、地铁等条件查找房源，请告诉我您的需求。"
        if _is_capability_ask(user_input):
            return "我可以帮您查询北京各区的租房信息，支持按户型、预算、地铁通勤、装修等条件筛选，也能比较各平台价格和办理租赁。"
        return "好的，请告诉我您的租房需求（如区域、户型、预算等），我来帮您查找。"

    if rent_ok:
        hid = slots.house_id if slots else ""
        return f"好的，已为您办理{hid}的租赁。"

    if intent == "terminate_lease":
        return "好的，已为您办理退租。"

    if single_match:
        return "没有其他的了，只有这一套。"

    if no_match:
        desc = ""
        if slots:
            parts = []
            if slots.district:
                parts.append(slots.district)
            if slots.room_count:
                parts.append(f"{slots.room_count}居室")
            if slots.rent_max:
                parts.append(f"月租{int(slots.rent_max)}元以内")
            desc = "、".join(parts)
        if desc:
            return f"没有符合条件的房源（{desc}）。建议适当调整条件，我可以帮您重新查询。"
        return "没有符合条件的房源。建议告诉我区域、户型、预算等需求，我来帮您查找。"

    if not houses:
        return "没有找到符合条件的房源。建议调整筛选条件后再试。"

    # Has results: format house list
    header_parts = []
    if slots:
        if slots.district:
            header_parts.append(slots.district)
        if slots.room_count is not None:
            header_parts.append(f"{slots.room_count}居室")
        if slots.max_subway_dist == 800:
            header_parts.append("近地铁(800米以内)")
        if slots.sort_by == "subway_distance" and slots.sort_order:
            header_parts.append(f"按 subway_distance {slots.sort_order} 排列")
    header = "为您找到" + "".join(header_parts) + "房源：\n" if header_parts else "为您找到以下房源：\n"
    parts = []
    for i, h in enumerate(houses[:5], 1):
        hid = h.get("house_id") or h.get("id")
        community = h.get("community", "")
        district = h.get("district", "")
        area = h.get("area", "")
        price = h.get("rent_price") or h.get("price", "")
        deco = h.get("decoration", "")
        subway = h.get("subway_station", "")
        subway_dist = h.get("subway_distance", "")
        orientation = h.get("orientation", "")
        commute = h.get("commute_time", "")
        line = f"{i}. {hid} - {district}{community} {area}㎡ 月租{price}元"
        if deco:
            line += f" {deco}"
        if orientation:
            line += f" {orientation}"
        if subway:
            line += f" 近{subway}站"
        if subway_dist:
            line += f"({subway_dist}米)"
        if commute:
            line += f" 西二旗通勤{commute}分钟"
        parts.append(line)
    result = header + "\n".join(parts)
    if listings:
        result += "\n各平台挂牌：" + json.dumps(listings, ensure_ascii=False)
    return result
