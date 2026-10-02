# report.py - turns Gemini's complaint text into clean, validated fields.
# No Streamlit in here, so it can be tested on its own.

import re

from prompts import CATEGORY_LIST, NO_ISSUE_TOKEN, NO_LOCATION_TOKEN, URGENCY_LIST

# (key, label) in the order they appear in a complaint
FIELDS = [
    ("subject", "SUBJECT"),
    ("category", "Category"),
    ("urgency", "Urgency"),
    ("location", "Location"),
    ("description", "Description"),
    ("risk", "Potential risk"),
    ("action", "Requested action"),
]
LABEL_TO_KEY = {label.lower(): key for key, label in FIELDS}

# Matches "Category: Road", "**Category:** Road", "- Category : Road", etc.
LABEL_LINE = re.compile(
    r"^[\s*_#>\-]*("
    + "|".join(re.escape(label) for _, label in FIELDS)
    + r")[\s*_]*:[\s*_]*(.*)$",
    re.IGNORECASE,
)

REQUIRED = ("location", "description")
DEFAULT_RISK = "Not specified."
DEFAULT_ACTION = "Please inspect the issue and take suitable action."
MAX_SUBJECT_LEN = 150
MAX_FIELD_LEN = 1500


def _strip_fences(text):
    """Remove a ``` code fence if Gemini wrapped the answer in one."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _flatten(value):
    return " ".join(value.split())


def _has_placeholder(value):
    """True for '<something>' left behind, or an empty / '...' value."""
    return bool(re.search(r"<[^<>]*>", value)) or value.strip(" .…") == ""


def _pick(value, options):
    """Return the option that appears first in value, or None."""
    best, best_pos = None, len(value) + 1
    for option in options:
        match = re.search(rf"\b{re.escape(option)}\b", value, re.IGNORECASE)
        if match and match.start() < best_pos:
            best, best_pos = option, match.start()
    return best


def _malformed(problem, raw):
    return {"status": "malformed", "problem": problem, "raw": raw or ""}


def parse_report(raw):
    """Parse Gemini's reply into one of four outcomes.

    Returns a dict with "status":
      "no_issue" / "no_location"  - Gemini returned a sentinel token
      "malformed"                 - unusable; has "problem" and "raw"
      "ok"                        - has "fields" (clean values) and "notes"
    """
    text = _strip_fences(raw or "")
    if not text:
        return _malformed("Gemini returned an empty reply.", raw)

    first_line = text.splitlines()[0].strip().strip("*_`. ")
    if first_line == NO_ISSUE_TOKEN:
        return {"status": "no_issue"}
    if first_line == NO_LOCATION_TOKEN:
        return {"status": "no_location"}

    # Collect "Label: value" blocks. Continuation lines are added to the
    # previous field, except for the subject, which must stay on one line.
    found = {}
    current = None
    for line in text.splitlines():
        match = LABEL_LINE.match(line)
        if match:
            key = LABEL_TO_KEY[match.group(1).lower()]
            if key in found:
                current = None  # repeated label: the first one wins
            else:
                found[key] = [match.group(2)]
                current = key
        elif current and current != "subject" and line.strip():
            found[current].append(line)

    values = {
        key: _flatten(" ".join(parts))[:MAX_FIELD_LEN] for key, parts in found.items()
    }
    usable = {k: v for k, v in values.items() if not _has_placeholder(v)}

    missing = [key for key in REQUIRED if key not in usable]
    if missing:
        return _malformed("Missing or unfilled: " + ", ".join(missing), raw)

    notes = []

    category = _pick(usable.get("category", ""), CATEGORY_LIST)
    if category is None:
        category = "Other"
        notes.append("The category was missing or unclear, so it was set to Other.")

    urgency = _pick(usable.get("urgency", ""), URGENCY_LIST)
    if urgency is None:
        urgency = "Medium"
        notes.append("The urgency was missing or unclear, so it was set to Medium.")

    risk = usable.get("risk")
    if risk is None:
        risk = DEFAULT_RISK
        notes.append("The potential risk was missing. Please review it.")

    action = usable.get("action")
    if action is None:
        action = DEFAULT_ACTION
        notes.append("The requested action was missing, so a default was used.")

    subject = usable.get("subject")
    if subject is None:
        subject = f"Civic Issue Report - {usable['location']}"
        notes.append("The subject line was missing, so a default was used.")

    return {
        "status": "ok",
        "fields": {
            "subject": subject[:MAX_SUBJECT_LEN],
            "category": category,
            "urgency": urgency,
            "location": usable["location"],
            "description": usable["description"],
            "risk": risk,
            "action": action,
        },
        "notes": notes,
    }


def build_report_text(fields):
    """Turn clean fields back into the canonical complaint text."""
    lines = []
    for key, label in FIELDS:
        value = fields[key]
        if key == "urgency":
            value = f"{value} (AI estimate)"
        lines.append(f"{label}: {value}")
    return "\n".join(lines)

# ---------- location backstop ----------

VAGUE_LOCATIONS = {
    "here", "there", "nearby", "near me", "near here", "my area", "my place",
    "my house", "my college", "this place", "unknown", "not provided",
    "n/a", "na", "none",
}
MIN_LOCATION_LEN = 5


def _norm(value):
    return " ".join(str(value).lower().split()).strip(" .,-;:")


def location_problem(location, area):
    """Return a message if the location is too vague, else None.
    This backs up the prompt rule that Gemini must ask for the exact location."""
    loc = _norm(location)
    if len(loc) < MIN_LOCATION_LEN or loc in VAGUE_LOCATIONS:
        return (
            "The location is too vague. Add a street, landmark, building "
            "or junction so the authority can find the problem."
        )
    if loc == _norm(area):
        return (
            "The location is only your general area. Add a street, landmark, "
            "building or junction so the authority can find the problem."
        )
    return None