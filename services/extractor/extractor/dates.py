"""Local dates read by the model become times with an offset (ADR-0007, point 2).

The model only reads the date; code adds the zone and the offset in force on that day.
"""
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_ZONE = 'Europe/Warsaw'
_LOCAL = re.compile(r'^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?)?$')


class BadDate(ValueError):
    """A date the model returned cannot be a real local time."""


def to_instant(local, zone=DEFAULT_ZONE):
    """'2026-04-10T07:25' -> ('2026-04-10T07:25:00+02:00', True); '2026-04-10' -> (midnight, False).

    In the hour repeated in autumn the earlier offset is used. A time in the hour skipped
    in spring does not exist and raises BadDate.
    """
    m = _LOCAL.match(local or '')
    if not m:
        raise BadDate('not YYYY-MM-DD or YYYY-MM-DDTHH:MM[:SS]')
    y, mo, d, hh, mm, ss = m.groups()
    try:
        day = date(int(y), int(mo), int(d))
        clock = time(int(hh), int(mm), int(ss or 0)) if hh is not None else time(0, 0)
    except ValueError:
        raise BadDate('no such date or time') from None
    tz = ZoneInfo(zone)
    naive = datetime.combine(day, clock)
    aware = naive.replace(tzinfo=tz, fold=0)
    # A time that does not exist does not survive a round trip through UTC.
    if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != naive:
        raise BadDate('the time does not exist in this zone (clocks went forward)')
    return aware.isoformat(timespec='seconds'), hh is not None


def offset_of(instant):
    return datetime.fromisoformat(instant).utcoffset() or timedelta(0)
