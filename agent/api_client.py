import requests
from typing import Any, Dict, List, Optional, Tuple

from . import config
from .config import API_TIMEOUT, BASE_URL, HEADERS_NO_USER, HEADERS_WITH_USER


def safe_api_call(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict] = None,
    timeout: float = API_TIMEOUT,
) -> Tuple[bool, Any]:
    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
        elif method.upper() == "POST":
            r = requests.post(url, headers=headers, params=params, json=json, timeout=timeout)
        else:
            return False, "Unsupported method"
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        if isinstance(data, dict) and data.get("code") == 400:
            return False, data.get("message", "请求参数错误")
        if r.status_code >= 400:
            return False, data if isinstance(data, str) else data.get("message", str(data))
        return True, data
    except requests.Timeout:
        return False, "服务超时"
    except Exception as e:
        return False, str(e)


class LandmarkAPI:
    def get_landmarks(
        self,
        category: Optional[str] = None,
        district: Optional[str] = None,
    ) -> List[dict]:
        params = {}
        if category:
            params["category"] = category
        if district:
            params["district"] = district
        ok, out = safe_api_call("GET", f"{BASE_URL}/api/landmarks", params=params, headers=HEADERS_NO_USER)
        if not ok:
            return []
        if isinstance(out, dict) and "data" in out:
            return out["data"] if isinstance(out["data"], list) else []
        return out if isinstance(out, list) else []

    def get_landmark_by_name(self, name: str) -> Optional[dict]:
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/landmarks/name/{requests.utils.quote(name)}",
            headers=HEADERS_NO_USER,
        )
        if not ok or not out:
            return None
        if isinstance(out, dict) and "data" in out:
            return out["data"]
        return out if isinstance(out, dict) else None

    def search_landmarks(
        self,
        q: str,
        category: Optional[str] = None,
        district: Optional[str] = None,
    ) -> List[dict]:
        params = {"q": q}
        if category:
            params["category"] = category
        if district:
            params["district"] = district
        ok, out = safe_api_call("GET", f"{BASE_URL}/api/landmarks/search", params=params, headers=HEADERS_NO_USER)
        if not ok:
            return []
        if isinstance(out, dict) and "data" in out:
            return out["data"] if isinstance(out["data"], list) else []
        return out if isinstance(out, list) else []

    def get_landmark_by_id(self, landmark_id: str) -> Optional[dict]:
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/landmarks/{landmark_id}",
            headers=HEADERS_NO_USER,
        )
        if not ok or not out:
            return None
        if isinstance(out, dict) and "data" in out:
            return out["data"]
        return out if isinstance(out, dict) else None

    def get_landmark_stats(self) -> dict:
        ok, out = safe_api_call("GET", f"{BASE_URL}/api/landmarks/stats", headers=HEADERS_NO_USER)
        if not ok:
            return {}
        return out.get("data", out) if isinstance(out, dict) else {}


class HouseAPI:
    def init_houses(self) -> dict:
        ok, out = safe_api_call("POST", f"{BASE_URL}/api/houses/init", headers=HEADERS_WITH_USER)
        if not ok:
            return {"success": False, "message": out}
        return out if isinstance(out, dict) else {"data": out}

    def get_house(self, house_id: str) -> Optional[dict]:
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/houses/{house_id}",
            headers=HEADERS_WITH_USER,
        )
        if not ok or not out:
            return None
        if isinstance(out, dict) and "data" in out:
            return out["data"]
        return out if isinstance(out, dict) else None

    def get_house_listings(self, house_id: str) -> Optional[dict]:
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/houses/listings/{house_id}",
            headers=HEADERS_WITH_USER,
        )
        if not ok:
            return None
        if isinstance(out, dict) and "data" in out:
            return out["data"]
        return out if isinstance(out, dict) else None

    def get_houses_by_community(
        self,
        community: str,
        listing_platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        params = {"community": community, "page": page, "page_size": page_size}
        if listing_platform:
            params["listing_platform"] = listing_platform
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/houses/by_community",
            params=params,
            headers=HEADERS_WITH_USER,
        )
        if not ok:
            return {"total": 0, "items": []}
        data = out.get("data", out) if isinstance(out, dict) else out
        if isinstance(data, dict):
            return {"total": data.get("total", 0), "items": data.get("items", [])}
        return {"total": 0, "items": []}

    def get_houses_by_platform(
        self,
        listing_platform: Optional[str] = None,
        district: Optional[str] = None,
        area: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[str] = None,
        rental_type: Optional[str] = None,
        decoration: Optional[str] = None,
        orientation: Optional[str] = None,
        elevator: Optional[str] = None,
        min_area: Optional[int] = None,
        max_area: Optional[int] = None,
        max_subway_dist: Optional[int] = None,
        subway_line: Optional[str] = None,
        subway_station: Optional[str] = None,
        utilities_type: Optional[str] = None,
        commute_to_xierqi_max: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        available_from_before: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        **kwargs: Any,
    ) -> dict:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if listing_platform:
            params["listing_platform"] = listing_platform
        if district:
            params["district"] = district
        if area:
            params["area"] = area
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if bedrooms is not None:
            params["bedrooms"] = str(bedrooms) if not isinstance(bedrooms, str) else bedrooms
        if rental_type:
            params["rental_type"] = rental_type
        if decoration:
            params["decoration"] = decoration
        if orientation:
            params["orientation"] = orientation
        if elevator is not None:
            params["elevator"] = "true" if elevator is True or elevator == "true" else "false"
        if min_area is not None:
            params["min_area"] = int(min_area)
        if max_area is not None:
            params["max_area"] = int(max_area)
        if max_subway_dist is not None:
            params["max_subway_dist"] = int(max_subway_dist)
        if subway_line:
            params["subway_line"] = subway_line
        if subway_station:
            params["subway_station"] = subway_station
        if utilities_type:
            params["utilities_type"] = utilities_type
        if commute_to_xierqi_max is not None:
            params["commute_to_xierqi_max"] = int(commute_to_xierqi_max)
        if sort_by:
            params["sort_by"] = sort_by
        if sort_order:
            params["sort_order"] = sort_order
        if available_from_before:
            params["available_from_before"] = available_from_before
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/houses/by_platform",
            params=params,
            headers=HEADERS_WITH_USER,
        )
        if not ok:
            return {"total": 0, "items": []}
        data = out.get("data", out) if isinstance(out, dict) else out
        if isinstance(data, dict):
            return {"total": data.get("total", 0), "items": data.get("items", [])}
        return {"total": 0, "items": []}

    def get_houses_nearby(
        self,
        landmark_id: str,
        max_distance: int = 2000,
        listing_platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        params = {"landmark_id": landmark_id, "max_distance": max_distance, "page": page, "page_size": page_size}
        if listing_platform:
            params["listing_platform"] = listing_platform
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/houses/nearby",
            params=params,
            headers=HEADERS_WITH_USER,
        )
        if not ok:
            return {"total": 0, "items": []}
        data = out.get("data", out) if isinstance(out, dict) else out
        if isinstance(data, dict):
            return {"total": data.get("total", 0), "items": data.get("items", [])}
        return {"total": 0, "items": []}

    def get_nearby_landmarks(
        self,
        community: str,
        type_: Optional[str] = None,
        max_distance_m: int = 3000,
    ) -> dict:
        params = {"community": community, "max_distance_m": max_distance_m}
        if type_:
            params["type"] = type_
        ok, out = safe_api_call(
            "GET",
            f"{BASE_URL}/api/houses/nearby_landmarks",
            params=params,
            headers=HEADERS_WITH_USER,
        )
        if not ok:
            return {"items": []}
        data = out.get("data", out) if isinstance(out, dict) else out
        if isinstance(data, dict):
            return {"items": data.get("items", [])}
        return {"items": []}

    def get_house_stats(self) -> dict:
        ok, out = safe_api_call("GET", f"{BASE_URL}/api/houses/stats", headers=HEADERS_WITH_USER)
        if not ok:
            return {}
        return out.get("data", out) if isinstance(out, dict) else {}

    def rent_house(self, house_id: str, listing_platform: str) -> Tuple[bool, Any]:
        return safe_api_call(
            "POST",
            f"{BASE_URL}/api/houses/{house_id}/rent",
            params={"listing_platform": listing_platform},
            headers=HEADERS_WITH_USER,
        )

    def terminate_house(self, house_id: str, listing_platform: str) -> Tuple[bool, Any]:
        return safe_api_call(
            "POST",
            f"{BASE_URL}/api/houses/{house_id}/terminate",
            params={"listing_platform": listing_platform},
            headers=HEADERS_WITH_USER,
        )

    def offline_house(self, house_id: str, listing_platform: str) -> Tuple[bool, Any]:
        return safe_api_call(
            "POST",
            f"{BASE_URL}/api/houses/{house_id}/offline",
            params={"listing_platform": listing_platform},
            headers=HEADERS_WITH_USER,
        )
