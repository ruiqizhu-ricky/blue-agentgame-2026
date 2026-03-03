import copy
import json
from typing import Any, Dict, List, Optional, Tuple

from .llm_client import call_llm, parse_intent_response
from .models import Intent, Slots

VALID_DISTRICTS = ["海淀", "朝阳", "通州", "昌平", "大兴", "房山", "西城", "丰台", "顺义", "东城"]
VALID_DECORATIONS = ["简装", "精装", "豪华", "毛坯", "空房"]
VALID_ORIENTATIONS = ["朝南", "朝北", "朝东", "朝西", "南北", "东西"]
VALID_PLATFORMS = ["链家", "安居客", "58同城"]

# 商圈/地名：用 API 的 area 参数而不是 district
BUSINESS_AREAS = {"望京", "国贸", "西二旗", "中关村", "上地", "五道口", "酒仙桥", "三里屯", "亚运村", "西北旺", "回龙观", "天通苑", "建国门", "四惠", "常营", "管庄", "望京SOHO"}
# 英文/拼音 → 中文区名
ENGLISH_TO_DISTRICT = {
    "haidian": "海淀", "chaoyang": "朝阳", "tongzhou": "通州", "changping": "昌平",
    "daxing": "大兴", "fangshan": "房山", "xicheng": "西城", "fengtai": "丰台",
    "shunyi": "顺义", "dongcheng": "东城",
}
DECORATION_ALIAS = {"精装修": "精装", "简装修": "简装"}


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


def normalize_district_and_area(district) -> tuple:
    """Returns (district, business_area). 商圈名归入 area 参数；行政区归入 district。"""
    if district is None:
        return None, None
    if isinstance(district, list):
        district = district[0] if district else None
        if not district:
            return None, None
    if not isinstance(district, str):
        return None, None
    s = district.strip().rstrip("区")
    # 英文/拼音
    low = s.lower()
    if low in ENGLISH_TO_DISTRICT:
        return ENGLISH_TO_DISTRICT[low], None
    # 正式行政区
    if s in VALID_DISTRICTS:
        return s, None
    # 商圈 → 用 area 参数
    if s in BUSINESS_AREAS:
        return None, s
    # 带"区"的行政区
    return (s if s else None), None


def _normalize_date(raw: str) -> Optional[str]:
    """Convert '3月' / '3月10日' / '2026-03-10' to YYYY-MM-DD format."""
    import re as _re
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if _re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    m = _re.match(r"(\d{1,2})月(\d{1,2})[日号]?", raw)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return f"2026-{month:02d}-{day:02d}"
    m = _re.match(r"(\d{1,2})月", raw)
    if m:
        month = int(m.group(1))
        import calendar
        last_day = calendar.monthrange(2026, month)[1]
        return f"2026-{month:02d}-{last_day:02d}"
    return raw


def normalize_slots(slots: Slots) -> Slots:
    """LLM 可能返回字符串类型的数字或「地铁」等，统一为正确类型避免 API 层 ValueError。"""
    d = slots.to_dict()
    # district / business_area 分离
    if d.get("district"):
        dist, area = normalize_district_and_area(d["district"])
        d["district"] = dist
        if area and not d.get("business_area"):
            d["business_area"] = area
    if d.get("decoration") and isinstance(d["decoration"], str):
        d["decoration"] = DECORATION_ALIAS.get(d["decoration"].strip(), d["decoration"].strip())
    # move_in_date → YYYY-MM-DD
    if d.get("move_in_date"):
        d["move_in_date"] = _normalize_date(d["move_in_date"])
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
规则: 仅打招呼/寒暄/问能做什么用 chat 且 slots 为空。找房/看房/查房源/有哪些房子/帮我找/推荐 用 query_house；问某套房详情或各平台价格用 compare_houses 填 house_id；租房用 rent_house；退租用 terminate_lease。
槽位(仅填提及的): district(行政区:海淀/朝阳/大兴等),business_area(商圈:望京/西二旗/国贸/上地等),room_count(int),room_counts(逗号分隔如"2,3"),rent_min,rent_max,area_min,area_max,decoration(精装/简装),orientation,has_elevator(bool),max_subway_dist(近地铁=800),subway_line(如13号线),subway_station(如车公庄站),utilities_type(如民水民电),max_commute_time,rental_type(整租/合租),listing_platform(链家/安居客/58同城),landmark_name,community_name,house_id(HF_xx),sort_by(rent_price/area/subway_distance),sort_order(asc/desc),move_in_date(如3月10日/2026-03-10)

用户: {user_input}

输出JSON: {{"intent":"","slots":{{}},"reference_to_last_result":false,"reference_index":null}}
"""
INTENT_PROMPT_WITH_CTX = """上轮房源IDs: {last_ids}
对话摘要: {history_summary}

从用户输入提取意图与槽位，输出纯 JSON。
意图: chat|query_house|query_landmark|query_nearby_landmark|compare_houses|rent_house|terminate_lease|offline_house|follow_up|confirm
规则: 仅打招呼/寒暄用 chat 且 slots 为空。找房/看房 用 query_house。问某套房详情/各平台价格 用 compare_houses 填 house_id。租房 rent_house，退租 terminate_lease。
槽位: district(行政区),business_area(商圈如望京/西二旗),room_count,room_counts("2,3"),rent_min,rent_max,decoration,subway_line(13号线),subway_station(车公庄站),utilities_type(民水民电),max_subway_dist(近地铁=800),sort_by,sort_order,community_name,house_id,listing_platform 等

用户: {user_input}

输出JSON: {{"intent":"","slots":{{}},"reference_to_last_result":false,"reference_index":null}}
"""


def parse_intent(
    user_input: str,
    history: List[Dict[str, str]],
    last_result_ids: List[str],
) -> Tuple[Intent, Slots, bool, Optional[int]]:
    """Returns (intent, slots, reference_to_last_result, reference_index). 仅带最近2轮上下文以省 token."""
    if history:
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
    raw = call_llm(messages, max_tokens=2048)
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
