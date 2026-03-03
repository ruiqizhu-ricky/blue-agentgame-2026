from typing import Any, Dict, List, Tuple

from .api_client import LandmarkAPI, HouseAPI
from .models import APICall

_landmark = LandmarkAPI()
_house = HouseAPI()


def _get_landmark_id_from_result(result: Any) -> str:
    if isinstance(result, dict):
        return result.get("id") or result.get("landmark_id") or ""
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0].get("id") or result[0].get("landmark_id") or ""
    return ""


def _get_items_from_house_result(result: Any) -> List[Dict]:
    if isinstance(result, dict) and "items" in result:
        return result["items"] or []
    return []


def _summarize_tool_result(name: str, params: Dict[str, Any], step_result: Any) -> Dict[str, Any]:
    """Build one entry for tool_results (判题/日志可见实际调用了哪些工具及结果)."""
    entry: Dict[str, Any] = {"tool": name, "params": params, "ok": step_result is not None}
    if step_result is None:
        return entry
    if isinstance(step_result, dict):
        if "items" in step_result:
            items = step_result.get("items") or []
            entry["total"] = step_result.get("total", len(items))
            entry["items_count"] = len(items)
        elif "house_id" in step_result or "id" in step_result:
            entry["house_id"] = step_result.get("house_id") or step_result.get("id")
        elif step_result.get("data"):
            entry["result"] = "data"
    return entry


def execute_calls(calls: List[APICall]) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """Execute API call sequence; returns (house_results, extra, tool_results)."""
    house_results: List[Dict[str, Any]] = []
    step_results: List[Any] = []
    extra: Dict[str, Any] = {}
    tool_results: List[Dict[str, Any]] = []

    for i, call in enumerate(calls):
        params = dict(call.params)
        # Resolve depends_on from previous step
        if call.depends_on and step_results:
            parts = call.depends_on.replace("step", "").split(".")
            step_idx = int(parts[0]) if parts[0].isdigit() else i - 1
            key = parts[1] if len(parts) > 1 else "id"
            if 0 <= step_idx < len(step_results):
                prev = step_results[step_idx]
                lid = _get_landmark_id_from_result(prev)
                if lid:
                    params["landmark_id"] = lid
        step_result = _execute_one(call.name, params)
        step_results.append(step_result)
        tool_results.append(_summarize_tool_result(call.name, params, step_result))
        items = _get_items_from_house_result(step_result)
        if items:
            house_results.extend(items)
        # Single house (get_house) or action result
        if call.name == "get_house" and step_result and isinstance(step_result, dict) and ("house_id" in step_result or "id" in step_result):
            house_results.append(step_result)
        if call.name == "get_house_listings" and step_result and isinstance(step_result, dict):
            extra["listings"] = step_result
        if call.name in ("rent_house", "terminate_house", "offline_house") and step_result:
            if isinstance(step_result, dict) and step_result.get("data"):
                house_results.append(step_result["data"])
            elif isinstance(step_result, dict):
                house_results.append(step_result)
    return house_results, extra, tool_results


def _execute_one(name: str, params: Dict[str, Any]) -> Any:
    if name == "get_landmark_by_name":
        out = _landmark.get_landmark_by_name(params.get("name", ""))
        return out
    if name == "get_landmarks":
        out = _landmark.get_landmarks(category=params.get("category"), district=params.get("district"))
        return out
    if name == "get_houses_nearby":
        landmark_id = params.get("landmark_id", "")
        out = _house.get_houses_nearby(
            landmark_id=landmark_id,
            max_distance=params.get("max_distance", 2000),
            listing_platform=params.get("listing_platform"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 10),
        )
        return out
    if name == "get_houses_by_community":
        out = _house.get_houses_by_community(
            community=params["community"],
            listing_platform=params.get("listing_platform"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 10),
        )
        return out
    if name == "get_houses_by_platform":
        out = _house.get_houses_by_platform(
            listing_platform=params.get("listing_platform"),
            district=params.get("district"),
            area=params.get("area"),
            min_price=params.get("min_price"),
            max_price=params.get("max_price"),
            bedrooms=params.get("bedrooms"),
            rental_type=params.get("rental_type"),
            decoration=params.get("decoration"),
            orientation=params.get("orientation"),
            elevator=params.get("elevator"),
            min_area=params.get("min_area"),
            max_area=params.get("max_area"),
            max_subway_dist=params.get("max_subway_dist"),
            subway_line=params.get("subway_line"),
            subway_station=params.get("subway_station"),
            utilities_type=params.get("utilities_type"),
            commute_to_xierqi_max=params.get("commute_to_xierqi_max"),
            sort_by=params.get("sort_by"),
            sort_order=params.get("sort_order"),
            available_from_before=params.get("available_from_before"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 10),
        )
        return out
    if name == "get_nearby_landmarks":
        out = _house.get_nearby_landmarks(
            community=params["community"],
            type_=params.get("type"),
            max_distance_m=params.get("max_distance_m", 3000),
        )
        return out
    if name == "get_house":
        out = _house.get_house(params.get("house_id", ""))
        return out
    if name == "get_house_listings":
        out = _house.get_house_listings(params.get("house_id", ""))
        return out
    if name == "rent_house":
        ok, out = _house.rent_house(
            house_id=params["house_id"],
            listing_platform=params.get("listing_platform", "安居客"),
        )
        return out if ok else None
    if name == "terminate_house":
        ok, out = _house.terminate_house(
            house_id=params["house_id"],
            listing_platform=params.get("listing_platform", "安居客"),
        )
        return out if ok else None
    if name == "offline_house":
        ok, out = _house.offline_house(
            house_id=params["house_id"],
            listing_platform=params.get("listing_platform", "安居客"),
        )
        return out if ok else None
    return None
