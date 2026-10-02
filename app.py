import re

import streamlit as st

from prompts import LANGUAGES, TONES

st.set_page_config(page_title="CivicSnap", page_icon="🏙️")

EMAIL_PATTERN = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+")


def is_valid_email(value):
    return bool(EMAIL_PATTERN.fullmatch(value))


def init_state():
    """Create every session-state key once, so later stages never hit a missing key."""
    defaults = {
        "onboarded": False,
        "profile": {},
        "chat": None,
        "messages": [],
        "report_draft": "",
        "report_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def show_onboarding():
    st.title("🏙️ CivicSnap")
    st.caption("Snap it. Describe it. Send a ready-to-submit civic complaint.")

    with st.form("onboarding_form"):
        name = st.text_input("Your name", max_chars=60)
        email = st.text_input(
            "Your email",
            max_chars=100,
            placeholder="you@gmail.com",
            help="Your report is always sent to this address.",
        )
        area = st.text_input(
            "Your city / area",
            max_chars=80,
            placeholder="e.g. Kolhapur, Shahupuri",
        )
        authority_email = st.text_input(
            "Authority email (optional)",
            max_chars=100,
            placeholder="Leave blank to send the report only to yourself",
            help="If filled, the report goes to this address and you are copied.",
        )
        col1, col2 = st.columns(2)
        with col1:
            tone = st.selectbox("Complaint tone", list(TONES))
        with col2:
            language = st.selectbox("Language", list(LANGUAGES))

        submitted = st.form_submit_button("Let's go 🚀")

    if not submitted:
        return

    name, email = name.strip(), email.strip()
    area, authority_email = area.strip(), authority_email.strip()

    errors = []
    if not name:
        errors.append("Please enter your name.")
    if not is_valid_email(email):
        errors.append("Please enter a valid email address for yourself.")
    if not area:
        errors.append("Please enter your city or area.")
    if authority_email and not is_valid_email(authority_email):
        errors.append("The authority email doesn't look valid. Fix it or leave it blank.")

    if errors:
        for message in errors:
            st.warning(message)
        return

    st.session_state.profile = {
        "name": name,
        "email": email,
        "area": area,
        "authority_email": authority_email,
        "tone": tone,
        "language": language,
    }
    st.session_state.onboarded = True
    st.rerun()


def show_placeholder():
    """Temporary screen so Stage 3 can be tested. Replaced by the chat in Stage 4."""
    profile = st.session_state.profile
    st.title("🏙️ CivicSnap")
    st.success("Stage 3 works: onboarding saved.")
    st.write(f"**Name:** {profile['name']}")
    st.write(f"**Your email:** {profile['email']}")
    st.write(f"**Area:** {profile['area']}")
    st.write(
        "**Authority email:** "
        + (profile["authority_email"] or "none (report goes only to you)")
    )
    st.write(f"**Tone:** {profile['tone']}")
    st.write(f"**Language:** {profile['language']}")
    st.button("Start over", on_click=reset_session)


init_state()

if not st.session_state.onboarded:
    show_onboarding()
    st.stop()

show_placeholder()