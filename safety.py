# safety.py - keyword backstop for the prompt's safety rule. No Streamlit here.
# It reads text only; hazards visible only in a photo rely on the prompt.

import re

SAFETY_MESSAGE = (
    "⚠️ Possible danger mentioned ({hazards}). Stay away from it, don't touch it, "
    "and keep others away. If anyone is in immediate danger, call 112 (India). "
    "You can still prepare a report from a safe distance."
)

# (label, patterns). English patterns are case-insensitive. Hindi/Marathi terms
# are plain substrings, because \b is unreliable with Devanagari.
HAZARDS = [
    (
        "exposed electrical wiring",
        [
            r"\b(exposed|live|bare|hanging|fallen|loose|dangling)\s+(electric\w*\s+)?(wires?|cables?)\b",
            r"\bspark(s|ing)\b",
            r"\b(electric\s+shock|electrocut\w*|short\s+circuit)",
            "नंगे तार",
            "उघडी तार",
        ],
    ),
    (
        "open manhole",
        [
            r"\b(open|uncovered|missing)\s+(manhole|man\s?hole|drain\s+cover|manhole\s+cover)",
            r"\bmanhole\s+cover\s+(is\s+)?(missing|broken|open|removed)",
            r"\bmanhole\s+is\s+open",
            "खुला मैनहोल",
            "खुले मैनहोल",
            "उघडे मॅनहोल",
        ],
    ),
    (
        "possible gas leak",
        [
            r"\bgas\s+(leak\w*|smell\w*)",
            r"\bsmell\w*\s+(of\s+)?gas\b",
            "गैस लीक",
            "गैस रिसाव",
            "गॅस गळती",
        ],
    ),
    (
        "collapse or sinkhole",
        [
            r"\bcollaps(e|ed|es|ing)\b",
            r"\bsink\s?hole",
            r"\bcaving\s+in\b",
        ],
    ),
    (
        "flooding near electricity",
        [
            r"\bflood\w*\b.{0,80}\b(electric\w*|wires?|poles?|transformer\w*)",
            r"\b(electric\w*|transformer\w*)\b.{0,80}\bflood\w*",
        ],
    ),
]

_COMPILED = [
    (label, [re.compile(p, re.IGNORECASE) for p in patterns])
    for label, patterns in HAZARDS
]


def find_hazards(text):
    """Return the labels of hazards mentioned in text (each listed once)."""
    if not text:
        return []
    return [
        label
        for label, patterns in _COMPILED
        if any(p.search(text) for p in patterns)
    ]