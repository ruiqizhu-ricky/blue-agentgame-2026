from typing import Any, Dict, List, Optional

from .models import APICall, Intent, Slots

# Map internal sort_by to API sort_by (price / area / subway)
SORT_BY_API = {
    "rent_price": "price",
    "price": "price",
    "area": "area",
    "subway_distance": "subway",
    "subway": "subway",
    "commute_time": "subway",
}


def _safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    """Coerce to int; invalid values (e.g. '地铁') return default."""
    if val is None:
        return default
    if isinstance(val, int):
        return val
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def slots_to_by_platform_params(slots: Slots) -> Dict[str, Any]:
    """Convert Slots to GET /api/houses/by_platform query params."""
    params: Dict[str, Any] = {}
    if slots.district:
        params["district"] = slots.district
    rc = _safe_int(slots.room_count)
    if rc is not None:
        params["bedrooms"] = str(rc)
    if slots.rent_min is not None:
        params["min_price"] = _safe_int(slots.rent_min, 0) or 0
    if slots.rent_max is not None:
        params["max_price"] = _safe_int(slots.rent_max, 99999) or 99999
    if slots.area_min is not None:
        params["min_area"] = _safe_int(slots.area_min, 0) or 0
    if slots.area_max is not None:
        params["max_area"] = _safe_int(slots.area_max, 99999) or 99999
    if slots.decoration:
        params["decoration"] = slots.decoration
    if slots.orientation:
        params["orientation"] = slots.orientation
    if slots.has_elevator is not None:
        params["elevator"] = "true" if slots.has_elevator else "false"
    msd = _safe_int(slots.max_subway_dist, 800)
    if msd is not None:
        params["max_subway_dist"] = msd
    mct = _safe_int(slots.max_commute_time)
    if mct is not None:
        params["commute_to_xierqi_max"] = mct
    if slots.rental_type:
        params["rental_type"] = slots.rental_type
    if slots.listing_platform:
        params["listing_platform"] = slots.listing_platform
    if slots.sort_by:
        params["sort_by"] = SORT_BY_API.get(slots.sort_by, slots.sort_by)
    if slots.sort_order:
        params["sort_order"] = slots.sort_order
    if slots.move_in_date:
        params["available_from_before"] = slots.move_in_date
    if slots.near_subway and "max_subway_dist" not in params:
        params["max_subway_dist"] = 800
    return params


def resolve_reference(
    user_input: str,
    last_results: List[Dict[str, Any]],
    reference_index: Optional[int],
) -> Optional[str]:
    """Resolve '第一套', '最近的', '最便宜的', '这套' to house_id."""
    if not last_results:
        return None
    if reference_index is not None and 0 <= reference_index < len(last_results):
        h = last_results[reference_index]
        return h.get("house_id") or h.get("id")
    text = user_input.strip()
    if "第一" in text or "第1" in text:
        h = last_results[0]
        return h.get("house_id") or h.get("id")
    if "第二" in text or "第2" in text and len(last_results) >= 2:
        h = last_results[1]
        return h.get("house_id") or h.get("id")
    if "最近" in text or "最近的那套" in text:
        # Assume last_results already sorted by subway_distance asc
        h = last_results[0]
        return h.get("house_id") or h.get("id")
    if "最便宜" in text:
        sorted_by_price = sorted(last_results, key=lambda x: x.get("rent_price", x.get("price", 999999)))
        if sorted_by_price:
            h = sorted_by_price[0]
            return h.get("house_id") or h.get("id")
    if "这套" in text or "这个" in text and len(last_results) == 1:
        h = last_results[0]
        return h.get("house_id") or h.get("id")
    return last_results[0].get("house_id") or last_results[0].get("id")


def plan_calls(intent: Intent, slots: Slots) -> List[APICall]:
    """Generate API call sequence for intent + slots."""
    calls: List[APICall] = []

    if intent == Intent.CHAT:
        return []

    if intent == Intent.QUERY_HOUSE or intent == Intent.FOLLOW_UP:
        if slots.landmark_name:
            calls.append(APICall("get_landmark_by_name", {"name": slots.landmark_name}))
            nearby_params = {"max_distance": 2000}
            if slots.listing_platform:
                nearby_params["listing_platform"] = slots.listing_platform
            calls.append(APICall("get_houses_nearby", nearby_params, depends_on="step0.id"))
            return calls
        if slots.community_name:
            params = {"community": slots.community_name}
            if slots.listing_platform:
                params["listing_platform"] = slots.listing_platform
            calls.append(APICall("get_houses_by_community", params))
            return calls
        params = slots_to_by_platform_params(slots)
        params.setdefault("page", 1)
        params.setdefault("page_size", 10)
        calls.append(APICall("get_houses_by_platform", params))
        return calls

    if intent == Intent.QUERY_LANDMARK:
        if slots.landmark_name:
            calls.append(APICall("get_landmark_by_name", {"name": slots.landmark_name}))
        else:
            calls.append(APICall("get_landmarks", {"category": slots.landmark_category, "district": slots.district}))
        return calls

    if intent == Intent.QUERY_NEARBY_LANDMARK:
        if slots.community_name:
            type_map = {"商超": "shopping", "公园": "park", "shopping": "shopping", "park": "park"}
            t = type_map.get(slots.landmark_category, "shopping")
            calls.append(APICall("get_nearby_landmarks", {"community": slots.community_name, "type": t}))
        return calls

    if intent == Intent.COMPARE_HOUSES and slots.house_id:
        calls.append(APICall("get_house", {"house_id": slots.house_id}))
        return calls

    if intent == Intent.RENT_HOUSE and slots.house_id:
        calls.append(APICall("rent_house", {"house_id": slots.house_id, "listing_platform": slots.listing_platform or "安居客"}))
        return calls

    if intent == Intent.TERMINATE_LEASE and slots.house_id:
        calls.append(APICall("terminate_house", {"house_id": slots.house_id, "listing_platform": slots.listing_platform or "安居客"}))
        return calls

    if intent == Intent.OFFLINE_HOUSE and slots.house_id:
        calls.append(APICall("offline_house", {"house_id": slots.house_id, "listing_platform": slots.listing_platform or "安居客"}))
        return calls

    return calls
