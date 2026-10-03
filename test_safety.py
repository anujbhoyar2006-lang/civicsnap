# test_safety.py - run with:  python test_safety.py
from safety import find_hazards


def test_exposed_wire_detected():
    for text in [
        "exposed wires hanging near the bus stop",
        "a live wire has fallen on the road",
        "electrical cables are sparking",
    ]:
        assert "exposed electrical wiring" in find_hazards(text), text


def test_open_manhole_detected():
    for text in [
        "open manhole outside the gate",
        "the manhole cover is missing",
        "an uncovered manhole on the road",
    ]:
        assert "open manhole" in find_hazards(text), text


def test_gas_leak_detected():
    for text in ["there is a gas leakage near the market", "I can smell of gas here"]:
        assert "possible gas leak" in find_hazards(text), text


def test_collapse_and_sinkhole_detected():
    for text in [
        "The wall has collapsed near the school",
        "A sinkhole has formed on the road",
        "the road is caving in",
    ]:
        assert "collapse or sinkhole" in find_hazards(text), text


def test_flood_near_electricity_detected():
    assert "flooding near electricity" in find_hazards("flooding near the electric pole")


def test_hindi_marathi_detected():
    assert "open manhole" in find_hazards("खुला मैनहोल है")
    assert "open manhole" in find_hazards("उघडे मॅनहोल आहे")
    assert "possible gas leak" in find_hazards("गैस लीक हो रहा है")
    assert "possible gas leak" in find_hazards("गॅस गळती होत आहे")


def test_ordinary_issues_not_flagged():
    for text in [
        "There is a pothole near my college",
        "broken streetlight on Station Road",
        "garbage pile near the market",
        "water leakage from the public tap",
        "Description: A large pothole appears hazardous for two-wheelers",
    ]:
        assert find_hazards(text) == [], text


def test_empty_and_none_are_safe():
    assert find_hazards("") == []
    assert find_hazards(None) == []


def test_each_hazard_listed_once():
    assert find_hazards("open manhole and another open manhole") == ["open manhole"]


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS", fn.__name__)
    print(f"\nAll {len(tests)} tests passed.")