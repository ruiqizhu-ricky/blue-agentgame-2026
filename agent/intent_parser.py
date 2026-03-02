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


INTENT_PROMPT = """你是一个租房需求解析器。根据用户输入和对话历史，提取以下信息，以 JSON 格式输出。

## 意图列表
- chat: 闲聊，不涉及租房查询
- query_house: 查询/筛选房源
- query_landmark: 查询地标信息
- query_nearby_landmark: 查询小区周边配套（商超/公园）
- compare_houses: 对比多个房源
- rent_house: 确认租房
- terminate_lease: 退租
- offline_house: 下架房源
- follow_up: 基于上一轮结果追问或追加条件
- confirm: 确认某个操作

## 槽位说明（只输出用户提到的或可推断的）
district: 行政区（海淀、朝阳、西城、东城等）
room_count: 居室数 1/2/3/4
rent_min, rent_max: 月租金范围（元）
area_min, area_max: 面积（平米）
decoration: 简装/精装/豪华/毛坯/空房
orientation: 朝南/朝北/朝东/朝西/南北/东西
has_elevator: true/false
max_subway_dist: 到地铁最大距离（米），近地铁填800，地铁可达填1000
max_commute_time: 到西二旗通勤时间上限（分钟）
rental_type: 整租/合租
listing_platform: 链家/安居客/58同城
landmark_name: 地标名称
community_name: 小区名
house_id: 房源ID
sort_by: 排序字段 rent_price/area/subway_distance
sort_order: asc/desc
move_in_date: 期望入住日期 YYYY-MM-DD
near_subway: 是否近地铁 true/false

## 近地铁规则
- 用户说"近地铁"/"离地铁近" → max_subway_dist = 800
- 用户说"地铁可达" → max_subway_dist = 1000
- 用户给出具体数值 → 使用该数值

## 用户输入
{user_input}

请输出严格 JSON，不要解释：
{{ "intent": "...", "slots": {{ ... }}, "reference_to_last_result": true/false, "reference_index": null或整数 }}
"""


def parse_intent(
    user_input: str,
    history: List[Dict[str, str]],
    last_result_ids: List[str],
) -> Tuple[Intent, Slots, bool, Optional[int]]:
    """Returns (intent, slots, reference_to_last_result, reference_index)."""
    prompt = INTENT_PROMPT.format(user_input=user_input)
    messages = [{"role": "user", "content": prompt}]
    if history:
        messages = [{"role": "user", "content": f"对话历史（供参考）：\n{json.dumps(history, ensure_ascii=False)}\n\n上一轮返回房源IDs：{last_result_ids}\n\n" + prompt}]
    raw = call_llm(messages)
    parsed = parse_intent_response(raw, user_input)
    intent_str = (parsed.get("intent") or "chat").strip().lower().replace("-", "_")
    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.CHAT
    slots_dict = parsed.get("slots") or {}
    slots = Slots.from_dict(slots_dict)
    ref = parsed.get("reference_to_last_result", False)
    ref_idx = parsed.get("reference_index")
    if ref_idx is not None and not isinstance(ref_idx, int):
        ref_idx = None
    return intent, slots, ref, ref_idx
