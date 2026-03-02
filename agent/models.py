from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Intent(Enum):
    CHAT = "chat"
    QUERY_HOUSE = "query_house"
    QUERY_LANDMARK = "query_landmark"
    QUERY_NEARBY_LANDMARK = "query_nearby_landmark"
    COMPARE_HOUSES = "compare_houses"
    RENT_HOUSE = "rent_house"
    TERMINATE_LEASE = "terminate_lease"
    OFFLINE_HOUSE = "offline_house"
    FOLLOW_UP = "follow_up"
    CONFIRM = "confirm"


@dataclass
class Slots:
    district: Optional[str] = None
    room_count: Optional[int] = None
    rent_min: Optional[float] = None
    rent_max: Optional[float] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    decoration: Optional[str] = None
    orientation: Optional[str] = None
    has_elevator: Optional[bool] = None
    max_subway_dist: Optional[int] = None
    max_commute_time: Optional[int] = None
    rental_type: Optional[str] = None
    listing_platform: Optional[str] = None
    landmark_name: Optional[str] = None
    landmark_category: Optional[str] = None
    community_name: Optional[str] = None
    house_id: Optional[str] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    move_in_date: Optional[str] = None
    near_subway: Optional[bool] = None
    tags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        for k, v in self.__dict__.items():
            if v is not None:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Slots":
        if not d:
            return cls()
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class APICall:
    name: str
    params: Dict[str, Any]
    depends_on: Optional[str] = None  # e.g. "step0.landmark_id"


@dataclass
class SessionState:
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_results: List[Dict[str, Any]] = field(default_factory=list)
    accumulated_filters: Optional[Slots] = None
    rented_houses: List[str] = field(default_factory=list)
    last_intent: Optional[Intent] = None
