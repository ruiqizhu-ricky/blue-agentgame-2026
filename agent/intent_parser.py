import copy
import json
from typing import Any, Dict, List, Optional, Tuple

from .llm_client import call_llm, parse_intent_response
from .models import Intent, Slots

VALID_DISTRICTS = ["海淀", "朝阳", "通州", "昌平", "大兴", "房山", "西城", "丰台", "顺义", "东城"]
VALID_DECORATIONS = ["简装", "精装", "豪华", "毛坯", "空房"]
VALID_ORIENTATIONS = ["朝南", "朝北", "朝东", "朝西", "南北", "东西"]
VALID_PLATFORMS = ["链家", "安居客", "58同城"]


def merge_slots(accumulated: Optional[Slots], new: Slots) -> Slots:
    """Merge new slots into accumulated; non-None in new overwrites."""
    if accumulated is None:
        return copy.deepcopy(new)
    merged = copy.deepcopy(accumulated)
    for f in Slots.__dataclass_fields__:
        v = getattr(new, f, None)
        if v is not None:
            setattr(merged, f, v)
    return merged


def normalize_slots(slots: Slots) -> Slots:
    """LLM 可能返回字符串类型的数字或「地铁」等，统一为正确类型避免 API 层 ValueError。"""
    d = slots.to_dict()
    # max_subway_dist: "地铁"/"近地铁" -> 800, "地铁可达" -> 1000, 数字 -> int
    v = d.get("max_subway_dist")
    if v is not None:
        if isinstance(v, int):
            pass
        elif isinstance(v, str):
            v = v.strip()
            if "可达" in v or v == "1000":
                d["max_subway_dist"] = 1000
            elif "近" in v or "地铁" in v or v == "800":
                d["max_subway_dist"] = 800
            else:
                try:
                    d["max_subway_dist"] = int(float(v))
                except (ValueError, TypeError):
                    d["max_subway_dist"] = 800
        else:
            try:
                d["max_subway_dist"] = int(v)
            except (ValueError, TypeError):
                d["max_subway_dist"] = 800
    # room_count, rent_min, rent_max, area_min, area_max, max_commute_time 转为数字
    for key, target_type in [
        ("room_count", int),
        ("rent_min", float),
        ("rent_max", float),
        ("area_min", float),
        ("area_max", float),
        ("max_commute_time", int),
    ]:
        v = d.get(key)
        if v is None:
            continue
        try:
            if target_type is int:
                d[key] = int(float(v)) if v != "" else None
            else:
                d[key] = target_type(v)
        except (ValueError, TypeError):
            d[key] = None
    return Slots.from_dict(d)


def validate_slots(slots: Slots) -> List[str]:
    errors = []
    if slots.district and slots.district not in VALID_DISTRICTS:
        errors.append(f"不支持的行政区: {slots.district}")
    if slots.decoration and slots.decoration not in VALID_DECORATIONS:
        errors.append(f"不支持的装修类型: {slots.decoration}")
    if slots.orientation and slots.orientation not in VALID_ORIENTATIONS:
        errors.append(f"不支持的朝向: {slots.orientation}")
    if slots.rent_min is not None and slots.rent_max is not None and slots.rent_min > slots.rent_max:
        errors.append("租金下限不能大于上限")
    if slots.listing_platform and slots.listing_platform not in VALID_PLATFORMS:
        errors.append(f"不支持的平台: {slots.listing_platform}")
    return errors


# 短版 prompt 节省 token（时间片公式 t=1+ceil(max(0,token-1000)*0.3)）
INTENT_PROMPT = """从用户输入提取意图与槽位，输出纯 JSON。

意图: chat|query_house|query_landmark|query_nearby_landmark|compare_houses|rent_house|terminate_lease|offline_house|follow_up|confirm
槽位(仅填提及或可推断): district,room_count,rent_min,rent_max,area_min,area_max,decoration,orientation,has_elevator,max_subway_dist(近地铁=800 地铁可达=1000),max_commute_time,rental_type,listing_platform,landmark_name,community_name,house_id,sort_by(rent_price/area/subway_distance),sort_order,move_in_date,near_subway

用户: {user_input}

输出JSON: {{"intent":"","slots":{{}},"reference_to_last_result":false,"reference_index":null}}
"""
INTENT_PROMPT_WITH_CTX = """上轮房源IDs: {last_ids}
对话摘要: {history_summary}

从用户输入提取意图与槽位，输出纯 JSON。
意图: chat|query_house|query_landmark|query_nearby_landmark|compare_houses|rent_house|terminate_lease|offline_house|follow_up|confirm
槽位: district,room_count,rent_min,rent_max,decoration,orientation,max_subway_dist(近地铁=800),sort_by,sort_order,community_name,house_id,listing_platform 等

用户: {user_input}

输出JSON: {{"intent":"","slots":{{}},"reference_to_last_result":false,"reference_index":null}}
"""


def parse_intent(
    user_input: str,
    history: List[Dict[str, str]],
    last_result_ids: List[str],
) -> Tuple[Intent, Slots, bool, Optional[int]]:
    """Returns (intent, slots, reference_to_last_result, reference_index). 仅带最近2轮上下文以省 token."""
    if history and last_result_ids is not None:
        # 最多 2 轮摘要，省 token
        summary_parts = []
        for m in history[-4:]:
            role = "U" if m.get("role") == "user" else "A"
            content = (m.get("content") or "")[:80]
            summary_parts.append(f"{role}:{content}")
        history_summary = " ".join(summary_parts)
        prompt = INTENT_PROMPT_WITH_CTX.format(
            last_ids=last_result_ids,
            history_summary=history_summary,
            user_input=user_input,
        )
    else:
        prompt = INTENT_PROMPT.format(user_input=user_input)
    messages = [{"role": "user", "content": prompt}]
    raw = call_llm(messages, max_tokens=512)
    parsed = parse_intent_response(raw, user_input)
    intent_str = (parsed.get("intent") or "chat").strip().lower().replace("-", "_")
    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.CHAT
    slots_dict = parsed.get("slots") or {}
    slots = Slots.from_dict(slots_dict)
    slots = normalize_slots(slots)
    ref = parsed.get("reference_to_last_result", False)
    ref_idx = parsed.get("reference_index")
    if ref_idx is not None and not isinstance(ref_idx, int):
        ref_idx = None
    return intent, slots, ref, ref_idx
