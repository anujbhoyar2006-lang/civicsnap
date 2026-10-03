# test_limits.py - run with:  python test_limits.py
from datetime import datetime

from limits import IST, DailyCounter

DAY1 = datetime(2026, 10, 3, 10, 0, tzinfo=IST)
DAY2 = datetime(2026, 10, 4, 10, 0, tzinfo=IST)


def test_allows_up_to_limit_then_refuses():
    counter = DailyCounter(3)
    assert [counter.try_take(DAY1) for _ in range(5)] == [True, True, True, False, False]


def test_resets_on_a_new_day():
    counter = DailyCounter(1)
    assert counter.try_take(DAY1)
    assert not counter.try_take(DAY1)
    assert counter.try_take(DAY2)


def test_zero_limit_blocks_everything():
    assert not DailyCounter(0).try_take(DAY1)


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS", fn.__name__)
    print(f"\nAll {len(tests)} tests passed.")