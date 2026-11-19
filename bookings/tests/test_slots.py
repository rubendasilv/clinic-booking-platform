from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from bookings.slots import generate_slots

LONDON = ZoneInfo("Europe/London")
DAY = date(2027, 3, 2)


def at(h, m=0):
    return datetime.combine(DAY, time(h, m), tzinfo=LONDON)


def slots(**overrides):
    args = {
        "day": DAY,
        "opens_at": time(10),
        "closes_at": time(12),
        "duration": timedelta(minutes=30),
        "buffer": timedelta(minutes=0),
        "busy": [],
        "tz": LONDON,
        "step": timedelta(minutes=30),
    }
    args.update(overrides)
    return generate_slots(**args)


def test_fills_opening_hours():
    assert slots() == [at(10), at(10, 30), at(11), at(11, 30)]


def test_closed_day_has_no_slots():
    assert slots(opens_at=None, closes_at=None) == []


def test_treatment_must_finish_by_closing():
    assert slots(duration=timedelta(minutes=45))[-1] == at(11)


def test_busy_period_is_skipped():
    assert at(10, 30) not in slots(busy=[(at(10, 30), at(11))])


def test_buffer_stops_back_to_back_clash():
    # a 30 min treatment + 15 min buffer starting 10:00 runs into an 10:30 booking
    result = slots(buffer=timedelta(minutes=15), busy=[(at(10, 30), at(11))])
    assert at(10) not in result
    assert at(11) in result


def test_buffer_may_run_past_closing():
    result = slots(buffer=timedelta(minutes=15))
    assert at(11, 30) in result


def test_minimum_notice():
    assert slots(earliest=at(11)) == [at(11), at(11, 30)]


def test_partial_overlap_is_blocked():
    result = slots(step=timedelta(minutes=15), busy=[(at(10, 45), at(11, 15))])
    assert at(10, 30) not in result
    assert at(11) not in result
    assert at(10) in result
    assert at(11, 15) in result


def test_clock_change_day_uses_local_time():
    # 28 Mar 2027 is the spring-forward Sunday in the UK
    spring = date(2027, 3, 28)
    result = generate_slots(
        day=spring,
        opens_at=time(10),
        closes_at=time(11),
        duration=timedelta(minutes=30),
        buffer=timedelta(0),
        busy=[],
        tz=LONDON,
        step=timedelta(minutes=30),
    )
    assert [s.hour for s in result] == [10, 10]
    assert result[0].utcoffset() == timedelta(hours=1)
