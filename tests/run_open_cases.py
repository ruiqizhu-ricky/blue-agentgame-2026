"""
Run open test cases: call agent handle() for each round and check message_contains + expectedHouses.
Requires simulation API (set SIMULATION_URL, USER_ID). Optional: LLM_API_BASE for real LLM.
"""
import json
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.main import handle


def load_cases():
    p = Path(__file__).parent / "open_cases.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    cases = load_cases()
    passed = 0
    failed = 0
    for case in cases:
        for r in case["rounds"]:
            session_id = r["session_id"]
            user_input = r["user_input"]
            expected = r["expected"]
            try:
                out = handle(session_id, user_input)
            except Exception as e:
                print(f"FAIL round session={session_id} input={user_input!r}: {e}")
                failed += 1
                continue
            message = out.get("message", "")
            houses = out.get("houses", [])

            msg_ok = all(s in message for s in expected.get("message_contains", []))
            houses_ok = houses == expected.get("expectedHouses", [])

            if msg_ok and houses_ok:
                print(f"PASS session={session_id} input={user_input[:30]}...")
                passed += 1
            else:
                print(f"FAIL session={session_id} input={user_input!r}")
                if not msg_ok:
                    missing = [s for s in expected.get("message_contains", []) if s not in message]
                    print(f"  message_contains missing: {missing}")
                if not houses_ok:
                    print(f"  expectedHouses: {expected.get('expectedHouses')} got: {houses}")
                failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
