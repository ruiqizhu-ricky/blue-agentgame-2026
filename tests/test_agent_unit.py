"""Unit tests: merge_slots, resolve_reference, slots_to_by_platform_params, no network."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.intent_parser import merge_slots
from agent.api_planner import resolve_reference, slots_to_by_platform_params
from agent.models import Slots, Intent
from agent.api_planner import plan_calls


def test_merge_slots():
    from agent.models import Slots
    acc = Slots(district="海淀", room_count=2)
    new = Slots(rent_max=5000)
    m = merge_slots(acc, new)
    assert m.district == "海淀"
    assert m.room_count == 2
    assert m.rent_max == 5000


def test_resolve_reference_first():
    last = [{"house_id": "HF_13"}, {"house_id": "HF_14"}]
    assert resolve_reference("第一套", last, None) == "HF_13"
    assert resolve_reference("就租第一套", last, None) == "HF_13"


def test_resolve_reference_nearest():
    last = [{"house_id": "HF_906", "subway_distance": 300}, {"house_id": "HF_1586", "subway_distance": 500}]
    assert resolve_reference("就租最近的那套吧", last, None) == "HF_906"
    assert resolve_reference("最近的那套", last, 0) == "HF_906"


def test_slots_to_by_platform_params():
    s = Slots(district="西城", room_count=1, max_subway_dist=800, sort_by="subway_distance", sort_order="asc")
    p = slots_to_by_platform_params(s)
    assert p["district"] == "西城"
    assert p["bedrooms"] == "1"
    assert p["max_subway_dist"] == 800
    assert p["sort_by"] == "subway"
    assert p["sort_order"] == "asc"


def test_plan_calls_query_house():
    s = Slots(district="东城", decoration="精装", room_count=2, rent_max=5000, max_subway_dist=500)
    calls = plan_calls(Intent.QUERY_HOUSE, s)
    assert len(calls) == 1
    assert calls[0].name == "get_houses_by_platform"
    assert calls[0].params["district"] == "东城"
    assert calls[0].params["max_price"] == 5000
    assert calls[0].params["max_subway_dist"] == 500
    assert calls[0].params["bedrooms"] == "2"


def test_plan_calls_rent():
    s = Slots(house_id="HF_906", listing_platform="安居客")
    calls = plan_calls(Intent.RENT_HOUSE, s)
    assert len(calls) == 1
    assert calls[0].name == "rent_house"
    assert calls[0].params["house_id"] == "HF_906"
    assert calls[0].params["listing_platform"] == "安居客"


def test_tools_defined():
    from agent.tools import TOOLS, SYSTEM_PROMPT
    assert len(TOOLS) >= 5
    assert "get_houses_by_platform" in [t["function"]["name"] for t in TOOLS]
    assert "租房顾问" in SYSTEM_PROMPT
