from typing import Any, Dict, List, Optional

from . import config
from .models import Slots

SORT_FIELD_MAP = {
    "价格从低到高": ("rent_price", "asc"),
    "价格从高到低": ("rent_price", "desc"),
    "离地铁从近到远": ("subway_distance", "asc"),
    "subway_distance_asc": ("subway_distance", "asc"),
    "离地铁从远到近": ("subway_distance", "desc"),
    "面积从大到小": ("area", "desc"),
    "面积从小到大": ("area", "asc"),
    "通勤时间从短到长": ("commute_time", "asc"),
    "price": ("rent_price", "asc"),
    "subway": ("subway_distance", "asc"),
}


def _house_id(h: Dict[str, Any]) -> str:
    return h.get("house_id") or h.get("id") or ""


def client_side_filter(houses: List[Dict[str, Any]], slots: Slots) -> List[Dict[str, Any]]:
    result = houses
    if slots.tags:
        result = [h for h in result if any(tag in (h.get("tags") or "") for tag in slots.tags)]
    if slots.move_in_date:
        result = [h for h in result if (h.get("available_date") or h.get("available_from") or "") <= slots.move_in_date]
    return result


def sort_houses(
    houses: List[Dict[str, Any]],
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not sort_by or not houses:
        return houses
    key_field = sort_by if sort_by in ("rent_price", "price", "area", "subway_distance", "commute_time") else "rent_price"
    if key_field == "price":
        key_field = "rent_price"
    reverse = sort_order == "desc"
    return sorted(
        houses,
        key=lambda h: h.get(key_field) if h.get(key_field) is not None else (float("inf") if not reverse else 0),
        reverse=reverse,
    )


def dedupe_by_house_id(houses: List[Dict[str, Any]], prefer_platform: Optional[str] = None) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict] = {}
    for h in houses:
        hid = _house_id(h)
        if not hid:
            continue
        if hid not in seen:
            seen[hid] = h
        else:
            # Prefer user's platform or 安居客
            p = h.get("listing_platform") or h.get("platform") or ""
            if prefer_platform and p == prefer_platform:
                seen[hid] = h
            elif not prefer_platform and p == "安居客":
                seen[hid] = h
    return list(seen.values())


def ensure_house_id(h: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(h)
    if "house_id" not in out and "id" in out:
        out["house_id"] = out["id"]
    return out


def process(
    houses: List[Dict[str, Any]],
    slots: Slots,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    max_houses: int = config.MAX_HOUSES,
) -> tuple[List[Dict[str, Any]], int]:
    """Filter, sort, dedupe, truncate. Returns (list of up to max_houses, total_before_truncate)."""
    for i, h in enumerate(houses):
        houses[i] = ensure_house_id(h)
    filtered = client_side_filter(houses, slots)
    sorted_list = sort_houses(filtered, sort_by=sort_by, sort_order=sort_order)
    deduped = dedupe_by_house_id(sorted_list, prefer_platform=slots.listing_platform)
    total = len(deduped)
    truncated = deduped[:max_houses]
    return truncated, total
