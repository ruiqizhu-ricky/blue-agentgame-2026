"""
Run open cases with mocked simulation API and LLM (no real server needed).
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Reset session state before importing main (so each test has fresh state)
import agent.session_manager as sm
sm._sessions.clear()

from agent.main import handle


# Predefined (tool_calls, final_content) for each round; mock call_llm uses these
_MOCK_LLM_RESPONSES = [
    # Case 1: 东城精装两居 5000以内 500米地铁 -> 无结果
    (
        [{"id": "tc1", "function": {"name": "get_houses_by_platform", "arguments": '{"district":"东城","decoration":"精装","bedrooms":"2","max_price":5000,"max_subway_dist":500}'}}],
        "没有符合您要求的房源。",
    ),
    # Case 2 round 1: 西城离地铁近一居室
    (
        [{"id": "tc2", "function": {"name": "get_houses_by_platform", "arguments": '{"district":"西城","bedrooms":"1","max_subway_dist":800,"sort_by":"subway_distance","sort_order":"asc"}'}}],
        "西城区1居室，800米地铁，subway_distance asc排序：HF_13 某小区 西城 40㎡ 4500元 精装 朝南 某站600米 通勤30分钟",
    ),
    # Case 2 round 2: 还有其他的吗
    (
        [{"id": "tc3", "function": {"name": "get_houses_by_platform", "arguments": '{"district":"西城","bedrooms":"1","max_subway_dist":800}'}}],
        "没有其他的了，只有这一套。HF_13 某小区 西城 40㎡ 4500元",
    ),
    # Case 3 round 1: 海淀离地铁近两居
    (
        [{"id": "tc4", "function": {"name": "get_houses_by_platform", "arguments": '{"district":"海淀","bedrooms":"2","max_subway_dist":800,"sort_by":"subway_distance","sort_order":"asc"}'}}],
        "海淀区2居室，800米地铁，subway_distance asc：HF_906 HF_1586 HF_1876 HF_706 HF_33 共5套",
    ),
    # Case 3 round 2: 就租最近的那套
    (
        [{"id": "tc5", "function": {"name": "rent_house", "arguments": '{"house_id":"HF_906","listing_platform":"安居客"}'}}],
        "好的，已为您办理HF_906的租赁。",
    ),
]
_mock_llm_idx = [0]


def _mock_call_llm(messages, *, temperature=0.2, max_tokens=1024, tools=None):
    """Mock LLM: first call returns tool_calls, second returns content."""
    has_tool_role = any(m.get("role") == "tool" for m in messages)
    idx = _mock_llm_idx[0]
    if idx >= len(_MOCK_LLM_RESPONSES):
        return {"content": "没有", "tool_calls": []}
    tool_calls, content = _MOCK_LLM_RESPONSES[idx]
    if has_tool_role:
        _mock_llm_idx[0] += 1
        return {"content": content, "tool_calls": []}
    return {"content": "", "tool_calls": tool_calls}


def _mock_by_platform(**params):
    """Return mock items based on query params (matches open cases)."""
    district = params.get("district")
    bedrooms = params.get("bedrooms")
    max_subway_dist = params.get("max_subway_dist")
    if district == "东城" and params.get("decoration") == "精装" and bedrooms == "2" and params.get("max_price") == 5000 and max_subway_dist == 500:
        return {"total": 0, "items": []}
    if district == "西城" and bedrooms == "1" and max_subway_dist == 800:
        return {
            "total": 1,
            "items": [{"house_id": "HF_13", "id": "HF_13", "district": "西城", "community": "某小区", "area": 40, "rent_price": 4500, "subway_distance": 600, "subway_station": "某站", "commute_time": 30}],
        }
    if district == "海淀" and bedrooms == "2" and max_subway_dist == 800:
        items = [
            {"house_id": "HF_906", "id": "HF_906", "district": "海淀", "community": "A", "area": 80, "rent_price": 6000, "subway_distance": 300, "subway_station": "西二旗", "commute_time": 10},
            {"house_id": "HF_1586", "id": "HF_1586", "district": "海淀", "community": "B", "area": 75, "rent_price": 5800, "subway_distance": 400, "subway_station": "西二旗", "commute_time": 12},
            {"house_id": "HF_1876", "id": "HF_1876", "district": "海淀", "community": "C", "area": 70, "rent_price": 5500, "subway_distance": 500, "subway_station": "西二旗", "commute_time": 14},
            {"house_id": "HF_706", "id": "HF_706", "district": "海淀", "community": "D", "area": 65, "rent_price": 5200, "subway_distance": 600, "subway_station": "西二旗", "commute_time": 16},
            {"house_id": "HF_33", "id": "HF_33", "district": "海淀", "community": "E", "area": 60, "rent_price": 5000, "subway_distance": 700, "subway_station": "西二旗", "commute_time": 18},
        ]
        return {"total": 5, "items": items}
    return {"total": 0, "items": []}


def _mock_init():
    return {"success": True}


def _mock_rent(house_id, listing_platform):
    return True, {"data": {"house_id": house_id}} if house_id else (False, "missing house_id")


def test_open_cases_mock():
    mock_house = type("MockHouse", (), {})()
    mock_house.init_houses = lambda: _mock_init()
    mock_house.get_houses_by_platform = lambda **kw: _mock_by_platform(**kw)
    mock_house.rent_house = lambda house_id, listing_platform: _mock_rent(house_id, listing_platform)
    mock_house.get_house = lambda house_id: None
    mock_house.get_houses_by_community = lambda **kw: {"total": 0, "items": []}
    mock_house.get_houses_nearby = lambda **kw: {"total": 0, "items": []}
    mock_house.get_nearby_landmarks = lambda **kw: {"items": []}
    mock_house.get_house_listings = lambda house_id: None
    mock_house.terminate_house = lambda house_id, listing_platform: (True, {})
    mock_house.offline_house = lambda house_id, listing_platform: (True, {})

    with patch("agent.main._house_api", mock_house), patch("agent.main.call_llm", side_effect=_mock_call_llm):
        cases_path = Path(__file__).parent / "open_cases.json"
        with open(cases_path, "r", encoding="utf-8") as f:
            cases = json.load(f)
        _mock_llm_idx[0] = 0
        for case in cases:
            sm._sessions.clear()
            for r in case["rounds"]:
                session_id = r["session_id"]
                user_input = r["user_input"]
                expected = r["expected"]
                out = handle(session_id, user_input)
                message = out.get("message", "")
                houses = out.get("houses", [])
                for s in expected.get("message_contains", []):
                    assert s in message, f"Round session={session_id!r} input={user_input[:40]!r}: missing {s!r} in message: {message[:300]!r}"
                exp_houses = expected.get("expectedHouses", [])
                assert houses == exp_houses, f"Round session={session_id!r}: expected houses {exp_houses} got {houses}"


if __name__ == "__main__":
    test_open_cases_mock()
    print("All open cases (mocked API) passed.")
