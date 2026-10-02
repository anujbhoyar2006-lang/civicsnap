# test_report.py - run with:  python test_report.py
from report import build_report_text, parse_report

GOOD = """SUBJECT: Road - Large pothole - Main gate, DKTE College
Category: Road
Urgency: High (AI estimate)
Location: Main gate, DKTE College, Ichalkaranji
Description: A large pothole appears to be present near the entrance.
Potential risk: It may be hazardous for two-wheelers and pedestrians.
Requested action: Please inspect and repair the road surface."""


def test_good_report():
    result = parse_report(GOOD)
    assert result["status"] == "ok"
    fields = result["fields"]
    assert fields["category"] == "Road"
    assert fields["urgency"] == "High"
    assert fields["location"].startswith("Main gate")
    assert result["notes"] == []


def test_sentinel_tokens():
    cases = [
        ("NO_ISSUE", "no_issue"),
        ("NO_LOCATION", "no_location"),
        ("NO_ISSUE.", "no_issue"),
        ("`NO_LOCATION`", "no_location"),
        ("NO_LOCATION\nI need more details.", "no_location"),
    ]
    for raw, status in cases:
        assert parse_report(raw)["status"] == status, raw


def test_markdown_and_fences():
    raw = "```text\n" + GOOD.replace("Category:", "**Category:**") + "\n```"
    result = parse_report(raw)
    assert result["status"] == "ok"
    assert result["fields"]["category"] == "Road"


def test_multiple_categories_takes_first():
    result = parse_report(GOOD.replace("Category: Road", "Category: Drainage / Road"))
    assert result["fields"]["category"] == "Drainage"


def test_unknown_category_becomes_other():
    result = parse_report(GOOD.replace("Category: Road", "Category: Potholes"))
    assert result["status"] == "ok"
    assert result["fields"]["category"] == "Other"
    assert len(result["notes"]) == 1


def test_placeholder_category_is_not_trusted():
    raw = GOOD.replace("Category: Road", "Category: <exactly one of: Road / Lighting>")
    result = parse_report(raw)
    assert result["fields"]["category"] == "Other"


def test_missing_urgency_defaults_to_medium():
    raw = "\n".join(l for l in GOOD.splitlines() if not l.startswith("Urgency"))
    result = parse_report(raw)
    assert result["status"] == "ok"
    assert result["fields"]["urgency"] == "Medium"
    assert len(result["notes"]) == 1


def test_placeholder_location_is_rejected():
    raw = GOOD.replace(
        "Main gate, DKTE College, Ichalkaranji", "<the exact location given by the user>"
    )
    assert parse_report(raw)["status"] == "malformed"


def test_multiline_description_is_joined():
    raw = GOOD.replace(
        "A large pothole appears to be present near the entrance.",
        "A large pothole appears\nto be present near the entrance.",
    )
    description = parse_report(raw)["fields"]["description"]
    assert description == "A large pothole appears to be present near the entrance."


def test_subject_stays_on_one_line():
    raw = GOOD.replace("Category: Road", "Bcc: evil@example.com\nCategory: Road")
    subject = parse_report(raw)["fields"]["subject"]
    assert "evil" not in subject and "Bcc" not in subject


def test_repeated_label_keeps_first():
    result = parse_report(GOOD + "\nLocation: Somewhere else entirely")
    assert result["fields"]["location"].startswith("Main gate")


def test_garbage_is_malformed():
    for raw in ["Sure! Here is a report about the pothole.", "", None]:
        assert parse_report(raw)["status"] == "malformed"


def test_hindi_content_with_english_labels():
    raw = GOOD.replace(
        "A large pothole appears to be present near the entrance.",
        "प्रवेशद्वार के पास एक बड़ा गड्ढा दिखाई देता है।",
    )
    result = parse_report(raw)
    assert result["status"] == "ok"
    assert "गड्ढा" in result["fields"]["description"]


def test_round_trip():
    first = parse_report(GOOD)
    second = parse_report(build_report_text(first["fields"]))
    assert second["status"] == "ok"
    assert second["fields"] == first["fields"]


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS", fn.__name__)
    print(f"\nAll {len(tests)} tests passed.")