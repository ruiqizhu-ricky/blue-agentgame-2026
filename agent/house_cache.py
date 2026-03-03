"""
Aggressive house caching: load ALL houses on first request, filter client-side.
Solves the problem of API queries returning 0 due to parameter mismatches.
"""
import logging
from typing import Any, Dict, List, Optional

from .api_client import HouseAPI

logger = logging.getLogger(__name__)

_house_api = HouseAPI()
_all_houses: List[Dict[str, Any]] = []
_loaded = False
_platforms = ["安居客", "链家", "58同城"]


def _load_all_houses() -> List[Dict[str, Any]]:
    """Load ALL houses from ALL platforms into cache."""
    all_items = []
    for platform in _platforms:
        try:
            result = _house_api.get_houses_by_platform(
                listing_platform=platform,
                page=1,
                page_size=10000,
            )
            items = result.get("items", [])
            total = result.get("total", 0)
            logger.info("Cache load: platform=%s total=%d items=%d", platform, total, len(items))
            for item in items:
                item["_listing_platform"] = platform
            all_items.extend(items)
        except Exception as e:
            logger.error("Cache load failed for %s: %s", platform, e)
    logger.info("Cache total: %d houses across %d platforms", len(all_items), len(_platforms))
    return all_items


def ensure_cache() -> List[Dict[str, Any]]:
    global _all_houses, _loaded
    if not _loaded:
        _all_houses = _load_all_houses()
        _loaded = True
        # Also run diagnostics
        try:
            stats = _house_api.get_house_stats()
            logger.info("House stats: %s", stats)
        except Exception as e:
            logger.error("Stats failed: %s", e)
    return _all_houses


def invalidate_cache():
    global _loaded
    _loaded = False


def search_houses(
    district: Optional[str] = None,
    business_area: Optional[str] = None,
    bedrooms: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_area: Optional[int] = None,
    max_area: Optional[int] = None,
    decoration: Optional[str] = None,
    orientation: Optional[str] = None,
    elevator: Optional[str] = None,
    max_subway_dist: Optional[int] = None,
    subway_line: Optional[str] = None,
    subway_station: Optional[str] = None,
    utilities_type: Optional[str] = None,
    rental_type: Optional[str] = None,
    listing_platform: Optional[str] = None,
    commute_to_xierqi_max: Optional[int] = None,
    available_from_before: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
) -> Dict[str, Any]:
    """Search cached houses with client-side filtering. Returns {"total": N, "items": [...]}."""
    houses = ensure_cache()
    results = list(houses)

    if listing_platform:
        results = [h for h in results if h.get("_listing_platform") == listing_platform or h.get("listing_platform") == listing_platform]

    if district:
        districts = [d.strip() for d in district.split(",")]
        results = [h for h in results if h.get("district") in districts]

    if business_area:
        areas = [a.strip() for a in business_area.split(",")]
        results = [h for h in results if any(a in (h.get("area") or h.get("business_area") or h.get("community") or "") for a in areas)]

    if bedrooms:
        bed_vals = [int(b.strip()) for b in bedrooms.split(",") if b.strip().isdigit()]
        if bed_vals:
            results = [h for h in results if _get_bedrooms(h) in bed_vals]

    if min_price is not None:
        results = [h for h in results if _get_price(h) >= min_price]
    if max_price is not None:
        results = [h for h in results if _get_price(h) <= max_price]

    if min_area is not None:
        results = [h for h in results if (h.get("area") or 0) >= min_area]
    if max_area is not None:
        results = [h for h in results if (h.get("area") or 99999) <= max_area]

    if decoration:
        results = [h for h in results if decoration in (h.get("decoration") or "")]
    if orientation:
        results = [h for h in results if orientation in (h.get("orientation") or "")]

    if elevator == "true":
        results = [h for h in results if h.get("elevator") or h.get("has_elevator")]
    elif elevator == "false":
        results = [h for h in results if not h.get("elevator") and not h.get("has_elevator")]

    if max_subway_dist is not None:
        results = [h for h in results if (h.get("subway_distance") or 99999) <= max_subway_dist]

    if subway_line:
        results = [h for h in results if subway_line in (h.get("subway_line") or h.get("subway_lines") or "")]

    if subway_station:
        results = [h for h in results if subway_station in (h.get("subway_station") or "")]

    if utilities_type:
        results = [h for h in results if utilities_type in (h.get("utilities_type") or h.get("water_electricity") or "")]

    if rental_type:
        results = [h for h in results if rental_type in (h.get("rental_type") or "")]

    if commute_to_xierqi_max is not None:
        results = [h for h in results if (h.get("commute_time") or h.get("commute_to_xierqi") or 999) <= commute_to_xierqi_max]

    if available_from_before:
        results = [h for h in results if (h.get("available_date") or h.get("available_from") or "9999") <= available_from_before]

    # Sort
    if sort_by:
        sort_key = {"price": "rent_price", "subway": "subway_distance", "area": "area"}.get(sort_by, sort_by)
        reverse = (sort_order == "desc")
        results.sort(key=lambda h: h.get(sort_key) if h.get(sort_key) is not None else (float("inf") if not reverse else 0), reverse=reverse)

    return {"total": len(results), "items": results}


def _get_bedrooms(h: Dict) -> int:
    v = h.get("bedrooms") or h.get("room_count")
    if v is None:
        layout = h.get("layout") or h.get("house_type") or ""
        if "1室" in layout or "一室" in layout or "一居" in layout:
            return 1
        if "2室" in layout or "两室" in layout or "两居" in layout or "二居" in layout:
            return 2
        if "3室" in layout or "三室" in layout or "三居" in layout:
            return 3
        return 0
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _get_price(h: Dict) -> float:
    return h.get("rent_price") or h.get("price") or h.get("monthly_rent") or 0
