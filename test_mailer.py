# test_mailer.py - run with:  python test_mailer.py
import email
import re
from datetime import datetime
from email import policy

from mailer import IST, build_email, make_report_id, recipients_for

SENDER = "civicsnap.app@gmail.com"
FIXED = datetime(2026, 10, 2, 15, 30, tzinfo=IST)
REPORT = "SUBJECT: Road - Pothole - DKTE gate\nCategory: Road\nUrgency: High (AI estimate)"
USER = "anuj@example.com"
PROFILE = {
    "name": "Anuj",
    "email": USER,
    "area": "Kolhapur",
    "authority_email": "",
    "tone": "Formal",
    "language": "English",
}


def make(authority="", subject="Road - Pothole - DKTE gate", text=REPORT):
    profile = dict(PROFILE, authority_email=authority)
    return build_email(SENDER, profile, subject, text, "CS-20261002-ABCD", FIXED)


def parsed(msg):
    return email.message_from_bytes(msg.as_bytes(), policy=policy.default)


def test_report_id_format():
    assert re.fullmatch(r"CS-20261002-[A-HJ-NP-Z2-9]{4}", make_report_id(FIXED))


def test_report_ids_differ():
    assert len({make_report_id(FIXED) for _ in range(20)}) > 1


def test_no_authority_goes_only_to_user():
    msg = make()
    assert str(msg["To"]) == USER
    assert msg["Cc"] is None
    assert recipients_for(USER, "") == (USER, None)


def test_authority_gets_it_and_user_is_cc():
    msg = make("ward@city.gov.in")
    assert str(msg["To"]) == "ward@city.gov.in"
    assert str(msg["Cc"]) == USER


def test_authority_same_as_user_is_not_duplicated():
    msg = make(USER.upper())
    assert str(msg["To"]) == USER
    assert msg["Cc"] is None


def test_reply_to_is_the_user():
    assert str(make("ward@city.gov.in")["Reply-To"]) == USER


def test_marathi_subject_survives():
    p = parsed(make(subject="Road - मोठा खड्डा - कॉलेज गेट"))
    assert "खड्डा" in str(p["Subject"])
    assert "CS-20261002-ABCD" in str(p["Subject"])


def test_hindi_body_survives():
    p = parsed(make(text="Description: कॉलेज के गेट के पास एक बड़ा गड्ढा है।"))
    assert "गड्ढा" in p.get_content()


def test_subject_newline_cannot_inject_a_header():
    p = parsed(make(subject="Road - pit\nBcc: evil@example.com"))
    assert p["Bcc"] is None
    assert "\n" not in str(p["Subject"])


def test_body_has_id_date_reporter_and_ai_note():
    body = parsed(make()).get_content()
    for expected in [
        "Report ID: CS-20261002-ABCD",
        "02 Oct 2026",
        "03:30 PM",
        "Anuj",
        "AI estimates",
    ]:
        assert expected in body, expected


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS", fn.__name__)
    print(f"\nAll {len(tests)} tests passed.")