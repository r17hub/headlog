"""Headlog alarm engine: parse time signals and generate alarm sequences."""

import re
from datetime import datetime, timedelta


DEFAULT_ALARM_CONFIG = {
    "sounds_enabled": True,
    "quiet_hours": {"start": "22:00", "end": "08:00"},
    "fuzzy_mappings": {
        "morning": "10:00",
        "noon": "12:00",
        "afternoon": "15:00",
        "evening": "18:00",
        "night": "21:00",
    },
    "open_todo_days": [2, 5, 10, 21],
    "day_bound_times": ["09:00", "14:00", "18:00"],
}


_DAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_MONTH_PATTERN = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"

_TIME_12H_RE = re.compile(
    r"\b(?:at\s+)?(\d{1,2})(?::([0-5]\d))?\s*([AaPp][Mm])\b"
)
_TIME_24H_RE = re.compile(
    r"\b(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b"
)
_DURATION_RE = re.compile(
    r"\b(?:in|within)\s+"
    r"(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*"
    r"(hours?|hrs?|hr|minutes?|mins?|min)|half\s+an?\s+hour|an?\s+hour)\b",
    re.IGNORECASE,
)
_RELATIVE_DAY_RE = re.compile(
    r"\b(day\s+after\s+tomorrow|tomorrow|today)\b",
    re.IGNORECASE,
)
_NAMED_DAY_RE = re.compile(
    r"\b(?:(this|next)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
_SPECIFIC_DATE_RE = re.compile(
    rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b"
    rf"|\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_PATTERN})\b",
    re.IGNORECASE,
)
_DEADLINE_PREFIX_RE = re.compile(r"\b(by|before|due|deadline)\b", re.IGNORECASE)

_FUZZY_PATTERNS = [
    (re.compile(r"\bbefore\s+lunch\b", re.IGNORECASE), "noon"),
    (re.compile(r"\b(?:by\s+)?morning\b|\bAM\b", re.IGNORECASE), "morning"),
    (re.compile(r"\b(?:by\s+)?noon\b|\blunchtime\b", re.IGNORECASE), "noon"),
    (re.compile(r"\b(?:by\s+)?afternoon\b", re.IGNORECASE), "afternoon"),
    (re.compile(r"\b(?:by\s+)?evening\b|\btonight\b|\bEOD\b|\bend\s+of\s+day\b", re.IGNORECASE), "evening"),
    (re.compile(r"\b(?:by\s+)?night\b|\bbefore\s+bed\b", re.IGNORECASE), "night"),
]

_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _merge_alarm_config(config):
    merged = {
        "sounds_enabled": DEFAULT_ALARM_CONFIG["sounds_enabled"],
        "quiet_hours": dict(DEFAULT_ALARM_CONFIG["quiet_hours"]),
        "fuzzy_mappings": dict(DEFAULT_ALARM_CONFIG["fuzzy_mappings"]),
        "open_todo_days": list(DEFAULT_ALARM_CONFIG["open_todo_days"]),
        "day_bound_times": list(DEFAULT_ALARM_CONFIG["day_bound_times"]),
    }
    if not isinstance(config, dict):
        return merged

    if "sounds_enabled" in config:
        merged["sounds_enabled"] = bool(config["sounds_enabled"])

    quiet_hours = config.get("quiet_hours")
    if isinstance(quiet_hours, dict):
        if "start" in quiet_hours:
            merged["quiet_hours"]["start"] = str(quiet_hours["start"])
        if "end" in quiet_hours:
            merged["quiet_hours"]["end"] = str(quiet_hours["end"])

    fuzzy = config.get("fuzzy_mappings")
    if isinstance(fuzzy, dict):
        for key in ("morning", "noon", "afternoon", "evening", "night"):
            if key in fuzzy:
                merged["fuzzy_mappings"][key] = str(fuzzy[key])

    open_days = config.get("open_todo_days")
    if isinstance(open_days, list) and len(open_days) >= 4:
        merged["open_todo_days"] = [int(v) for v in open_days[:4]]

    day_times = config.get("day_bound_times")
    if isinstance(day_times, list) and len(day_times) >= 3:
        merged["day_bound_times"] = [str(v) for v in day_times[:3]]

    return merged


def _parse_explicit_time(text):
    """Parse explicit clock times like 'at 4pm' or 'at 16:00'."""
    twelve = _TIME_12H_RE.search(text)
    twenty_four = _TIME_24H_RE.search(text)

    match = None
    kind = None
    if twelve and twenty_four:
        if twelve.start() <= twenty_four.start():
            match = twelve
            kind = "12h"
        else:
            match = twenty_four
            kind = "24h"
    elif twelve:
        match = twelve
        kind = "12h"
    elif twenty_four:
        match = twenty_four
        kind = "24h"

    if not match:
        return None

    if kind == "12h":
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = match.group(3).lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
    else:
        hour = int(match.group(1))
        minute = int(match.group(2))

    return hour, minute, match.group(0)


def _parse_duration(text, now):
    """Parse duration phrases like 'in 30 minutes'."""
    match = _DURATION_RE.search(text)
    if not match:
        return None

    raw = match.group(0)
    raw_lower = raw.lower()

    if "half" in raw_lower:
        return now + timedelta(minutes=30), raw
    if "an hour" in raw_lower:
        return now + timedelta(hours=1), raw

    number_token = (match.group(1) or "").lower()
    if number_token.isdigit():
        number = int(number_token)
    else:
        number = _NUMBER_WORDS.get(number_token)
    if number is None:
        return None

    unit = (match.group(2) or "").lower()
    if unit.startswith("h"):
        return now + timedelta(hours=number), raw
    return now + timedelta(minutes=number), raw


def _parse_relative_day(text, now):
    """Parse relative days: today, tomorrow, day after tomorrow."""
    match = _RELATIVE_DAY_RE.search(text)
    if not match:
        return None

    token = match.group(1).lower()
    if token == "today":
        return now.date(), match.group(0)
    if token == "tomorrow":
        return now.date() + timedelta(days=1), match.group(0)
    return now.date() + timedelta(days=2), match.group(0)


def _parse_named_day(text, now):
    """Parse weekday phrases like Friday, this Friday, next Wednesday."""
    match = _NAMED_DAY_RE.search(text)
    if not match:
        return None

    prefix = (match.group(1) or "").lower()
    day_name = match.group(2).lower()

    current_idx = now.weekday()
    target_idx = _DAY_NAMES[day_name]

    if prefix == "next":
        days_to_next_monday = (7 - current_idx) % 7
        if days_to_next_monday == 0:
            days_to_next_monday = 7
        days_ahead = days_to_next_monday + target_idx
    else:
        days_ahead = (target_idx - current_idx) % 7

    return now.date() + timedelta(days=days_ahead), match.group(0)


def _parse_specific_date(text, now, rollover_if_past=True):
    """Parse month/day forms like 'March 30' and '30th March'."""
    match = _SPECIFIC_DATE_RE.search(text)
    if not match:
        return None

    month = None
    day = None

    if match.group(1) and match.group(2):
        month = _MONTH_NAMES[match.group(1).lower()]
        day = int(match.group(2))
    elif match.group(3) and match.group(4):
        day = int(match.group(3))
        month = _MONTH_NAMES[match.group(4).lower()]

    if month is None or day is None:
        return None

    year = now.year
    try:
        target = datetime(year, month, day).date()
    except ValueError:
        return None

    if target < now.date() and rollover_if_past:
        try:
            target = datetime(year + 1, month, day).date()
        except ValueError:
            return None

    return target, match.group(0)


def _parse_fuzzy_time(text, config):
    """Parse fuzzy time-of-day phrases."""
    mappings = config["fuzzy_mappings"]
    best = None
    for pattern, key in _FUZZY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if best is None or match.start() < best[0].start():
            best = (match, key)

    if not best:
        return None

    match, key = best
    hh, mm = (mappings.get(key, "18:00")).split(":")
    return int(hh), int(mm), match.group(0)


def parse_time_signal(text, now=None, config=None):
    """Parse thought text into time zone and anchor metadata."""
    if now is None:
        now = datetime.now()
    cfg = _merge_alarm_config(config)

    result = {
        "zone": "open_todo",
        "anchor": None,
        "has_date": False,
        "has_time": False,
        "raw_match": None,
    }

    explicit = _parse_explicit_time(text)

    # Priority 2 (duration) applies only when explicit clock time is not present.
    if explicit is None:
        duration = _parse_duration(text, now)
        if duration:
            result["zone"] = "pinned"
            result["anchor"] = duration[0]
            result["has_date"] = True
            result["has_time"] = True
            result["raw_match"] = duration[1]
            return result

    has_deadline_phrase = bool(_DEADLINE_PREFIX_RE.search(text))

    parsed_date = None
    date_match = None

    # Rules 3–5 for date extraction
    relative = _parse_relative_day(text, now)
    if relative:
        parsed_date, date_match = relative

    if parsed_date is None:
        named = _parse_named_day(text, now)
        if named:
            parsed_date, date_match = named

    if parsed_date is None:
        # Edge case: deadline dates in the past should not auto-roll to next year.
        specific = _parse_specific_date(
            text,
            now,
            rollover_if_past=not has_deadline_phrase,
        )
        if specific:
            parsed_date, date_match = specific

    parsed_fuzzy = _parse_fuzzy_time(text, cfg)

    if explicit and parsed_date:
        hh, mm, time_match = explicit
        result["zone"] = "pinned"
        result["anchor"] = datetime(parsed_date.year, parsed_date.month, parsed_date.day, hh, mm)
        result["has_date"] = True
        result["has_time"] = True
        result["raw_match"] = f"{date_match} {time_match}"
        return result

    if explicit:
        hh, mm, time_match = explicit
        anchor = datetime(now.year, now.month, now.day, hh, mm)
        if anchor <= now:
            anchor = anchor + timedelta(days=1)
        result["zone"] = "pinned"
        result["anchor"] = anchor
        result["has_date"] = False
        result["has_time"] = True
        result["raw_match"] = time_match
        return result

    if parsed_date and parsed_fuzzy:
        hh, mm, fuzzy_match = parsed_fuzzy
        result["zone"] = "soft"
        result["anchor"] = datetime(parsed_date.year, parsed_date.month, parsed_date.day, hh, mm)
        result["has_date"] = True
        result["has_time"] = False
        result["raw_match"] = f"{date_match} {fuzzy_match}"
        return result

    if parsed_date:
        # Rule 6: deadline phrase over date defaults to day_bound.
        result["zone"] = "day_bound"
        result["anchor"] = datetime(parsed_date.year, parsed_date.month, parsed_date.day, 23, 59)
        result["has_date"] = True
        result["has_time"] = False
        result["raw_match"] = date_match
        return result

    if parsed_fuzzy:
        hh, mm, fuzzy_match = parsed_fuzzy
        anchor = datetime(now.year, now.month, now.day, hh, mm)
        if anchor <= now:
            anchor = anchor + timedelta(days=1)
        result["zone"] = "soft"
        result["anchor"] = anchor
        result["has_date"] = False
        result["has_time"] = False
        result["raw_match"] = fuzzy_match
        return result

    return result


def _truncate_text(text, max_chars=80):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _time_of_day(target_date, hhmm):
    hour, minute = [int(x) for x in hhmm.split(":")]
    return datetime(target_date.year, target_date.month, target_date.day, hour, minute)


def generate_alarm_sequence(
    parsed_signal,
    thought_text,
    now=None,
    config=None,
    created_at=None,
    is_private=False,
):
    """Generate alarm rows based on parsed signal and zone rules."""
    if now is None:
        now = datetime.now()
    if created_at is None:
        created_at = now

    cfg = _merge_alarm_config(config)

    zone = parsed_signal.get("zone", "open_todo")
    anchor = parsed_signal.get("anchor")

    display_text = "Tap to view in Headlog" if is_private else _truncate_text(thought_text, 80)
    alarms = []

    if zone == "pinned" and anchor:
        # Optional day-before nudge for future-date anchors.
        if anchor.date() > now.date():
            tomorrow_nudge = datetime(anchor.year, anchor.month, anchor.day, 20, 0) - timedelta(days=1)
            alarms.append({
                "sequence_index": 4,
                "fire_at": tomorrow_nudge.isoformat(),
                "tone": "gentle",
                "message": f"Tomorrow: {display_text}",
                "zone": "pinned",
            })

        final_nudge = anchor - timedelta(minutes=3)
        if final_nudge <= now and anchor > now:
            # If the event is very soon (e.g., "in 2 minutes"), keep one future ping.
            final_nudge = anchor

        alarms.extend([
            {
                "sequence_index": 1,
                "fire_at": (anchor - timedelta(minutes=60)).isoformat(),
                "tone": "gentle",
                "message": f"In 60 minutes: {display_text}",
                "zone": "pinned",
            },
            {
                "sequence_index": 2,
                "fire_at": (anchor - timedelta(minutes=15)).isoformat(),
                "tone": "warm",
                "message": f"In 15 minutes: {display_text}",
                "zone": "pinned",
            },
            {
                "sequence_index": 3,
                "fire_at": final_nudge.isoformat(),
                "tone": "sharp",
                "message": f"Starting now: {display_text}",
                "zone": "pinned",
            },
        ])

    elif zone == "day_bound" and anchor:
        deadline_day = anchor.date()
        if deadline_day < now.date():
            return []

        day_bound_times = cfg["day_bound_times"]
        deadline_morning = _time_of_day(deadline_day, day_bound_times[0])
        midpoint = now + (deadline_morning - now) / 2

        if now.date() < deadline_day and (midpoint - now) >= timedelta(days=2):
            alarms.append({
                "sequence_index": 1,
                "fire_at": midpoint.isoformat(),
                "tone": "gentle",
                "message": f"Halfway to deadline: {display_text}",
                "zone": "day_bound",
            })

        if now.date() < deadline_day:
            due_tomorrow = datetime(deadline_day.year, deadline_day.month, deadline_day.day, 20, 0) - timedelta(days=1)
            alarms.append({
                "sequence_index": 2,
                "fire_at": due_tomorrow.isoformat(),
                "tone": "warm",
                "message": f"Due tomorrow: {display_text}",
                "zone": "day_bound",
            })

        alarms.extend([
            {
                "sequence_index": 3,
                "fire_at": _time_of_day(deadline_day, day_bound_times[0]).isoformat(),
                "tone": "firm",
                "message": f"Due today: {display_text}",
                "zone": "day_bound",
            },
            {
                "sequence_index": 4,
                "fire_at": _time_of_day(deadline_day, day_bound_times[1]).isoformat(),
                "tone": "urgent",
                "message": f"Still due today: {display_text}",
                "zone": "day_bound",
            },
            {
                "sequence_index": 5,
                "fire_at": _time_of_day(deadline_day, day_bound_times[2]).isoformat(),
                "tone": "urgent",
                "message": f"Deadline tonight: {display_text}",
                "zone": "day_bound",
            },
        ])

    elif zone == "soft" and anchor:
        day_start = datetime(anchor.year, anchor.month, anchor.day, 9, 0)
        candidates = [
            {
                "sequence_index": 1,
                "fire_at": max(anchor - timedelta(hours=8), day_start),
                "tone": "gentle",
                "message": f"On your plate today: {display_text}",
                "zone": "soft",
            },
            {
                "sequence_index": 2,
                "fire_at": anchor - timedelta(hours=4),
                "tone": "warm",
                "message": f"Still on your plate: {display_text}",
                "zone": "soft",
            },
            {
                "sequence_index": 3,
                "fire_at": anchor - timedelta(hours=1),
                "tone": "firm",
                "message": f"Time to do this: {display_text}",
                "zone": "soft",
            },
        ]

        # Clamp before 09:00 to 09:00.
        for alarm in candidates:
            dt = alarm["fire_at"]
            if dt < day_start:
                alarm["fire_at"] = day_start

        candidates.sort(key=lambda a: a["fire_at"])

        # Merge alarms that are within 30 minutes (keep the later one).
        merged = []
        for alarm in candidates:
            if merged:
                previous = merged[-1]
                if (alarm["fire_at"] - previous["fire_at"]) <= timedelta(minutes=30):
                    merged[-1] = alarm
                    continue
            merged.append(alarm)

        alarms = [
            {
                "sequence_index": alarm["sequence_index"],
                "fire_at": alarm["fire_at"].isoformat(),
                "tone": alarm["tone"],
                "message": alarm["message"],
                "zone": alarm["zone"],
            }
            for alarm in merged
        ]

    elif zone == "open_todo":
        decay_days = cfg["open_todo_days"]
        messages = [
            f"Still on your list: {display_text}",
            f"Open for {decay_days[1]} days: {display_text}",
            f"{decay_days[2]} days — still relevant? {display_text}",
            f"{max(1, decay_days[3] // 7)} weeks old — act or archive? {display_text}",
        ]
        tones = ["gentle", "warm", "firm", "warm"]
        for idx, day_count in enumerate(decay_days):
            fire_dt = datetime(
                created_at.year,
                created_at.month,
                created_at.day,
                10,
                0,
            ) + timedelta(days=day_count)
            alarms.append({
                "sequence_index": idx + 1,
                "fire_at": fire_dt.isoformat(),
                "tone": tones[idx],
                "message": messages[idx],
                "zone": "open_todo",
            })

    # Skip past alarms.
    upcoming = []
    for alarm in alarms:
        fire_dt = datetime.fromisoformat(alarm["fire_at"])
        if fire_dt >= now:
            upcoming.append(alarm)

    if not upcoming:
        return []

    upcoming.sort(key=lambda alarm: alarm["fire_at"])

    if is_private:
        upcoming[0]["message"] = "🔒 " + upcoming[0]["message"]

    return upcoming


if __name__ == "__main__":
    now = datetime(2026, 3, 30, 9, 0, 0)  # Monday 9am

    tests = [
        ("meeting at 4pm", "pinned", True),
        ("call at 11:30am", "pinned", True),
        ("dentist tomorrow at 2pm", "pinned", True),
        ("submit report by Friday", "day_bound", True),
        ("due March 30", "day_bound", True),
        ("finish slides by evening", "soft", True),
        ("handle before lunch", "soft", True),
        ("tomorrow morning", "soft", True),
        ("in 30 minutes", "pinned", True),
        ("in 2 hours", "pinned", True),
        ("fix the login bug", "open_todo", True),
        ("read that book on stoicism", "open_todo", True),
        ("meeting at 4pm on Friday", "pinned", True),
        ("by Friday", "day_bound", True),
        ("call Mom today", "day_bound", True),
        ("before bed", "soft", True),
        ("standup at 16:00", "pinned", True),
    ]

    print("Time parser tests:\n")
    passed = 0
    for text, expected_zone, _ in tests:
        result = parse_time_signal(text, now=now)
        status = "✓" if result["zone"] == expected_zone else "✗"
        if status == "✓":
            passed += 1
        print(f"  {status} '{text}' -> {result['zone']} (expected {expected_zone})")

    print(f"\n{passed}/{len(tests)} parser tests passed\n")

    print("Alarm generator smoke tests:\n")
    parser_cases = [
        "meeting at 4pm",
        "submit report by Friday",
        "finish slides by evening",
        "fix the login bug",
    ]
    for text in parser_cases:
        parsed = parse_time_signal(text, now=now)
        alarms = generate_alarm_sequence(parsed, text, now=now)
        print(f"  - '{text}' -> zone={parsed['zone']} alarms={len(alarms)}")
