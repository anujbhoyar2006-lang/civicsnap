import re

import streamlit as st
from google import genai
from google.genai import types

from prompts import (
    LANGUAGES,
    TONES,
    WELCOME_MESSAGE_TEMPLATE,
    build_system_prompt,
)

MODEL_NAME = "gemini-3.5-flash"
MAX_PHOTO_MB = 10
DEFAULT_PHOTO_PROMPT = (
    "Here is a photo of a possible civic issue. "
    "Tell me what you see and what you need from me next."
)

st.set_page_config(page_title="CivicSnap", page_icon="🏙️")

EMAIL_PATTERN = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+")


# ---------- helpers ----------

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


@st.cache_resource
def get_gemini_client():
    """Built once and reused. Streamlit reruns the script on every click, and a
    client created as a plain variable would be rebuilt and closed each time."""
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def ensure_chat():
    """Create the Gemini chat once per session, with the user's tone/language/area."""
    if st.session_state.chat is None:
        p = st.session_state.profile
        st.session_state.chat = gemini_client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=build_system_prompt(
                    p["tone"], p["language"], p["area"]
                )
            ),
        )


def ask_gemini(parts):
    """Send one message to the chat. Returns (ok, text)."""
    try:
        reply = st.session_state.chat.send_message(parts)
        text = (reply.text or "").strip()
        if not text:
            return False, "Gemini returned an empty reply. Please try again."
        return True, text
    except Exception as error:
        return False, f"Something went wrong talking to Gemini: {error}"


# ---------- chat display ----------

def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            # Two trailing spaces + newline = a real line break in markdown,
            # so complaint drafts keep one field per line.
            st.write(message["content"].replace("\n", "  \n"))
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})
    render_message(st.session_state.messages[-1])


def handle_input(user_input):
    if not user_input:
        return

    text = (user_input.text or "").strip()
    photo = user_input.files[0] if user_input.files else None

    if photo is None and not text:
        return

    if photo is not None and photo.size > MAX_PHOTO_MB * 1024 * 1024:
        st.warning(f"That photo is larger than {MAX_PHOTO_MB} MB. Please use a smaller one.")
        return

    parts = []
    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(
            types.Part.from_bytes(data=photo_bytes, mime_type=photo.type or "image/jpeg")
        )
    if text:
        add_message("user", "text", text)
        parts.append(text)
    else:
        parts.append(DEFAULT_PHOTO_PROMPT)

    with st.spinner("Looking into it..."):
        ok, answer = ask_gemini(parts)

    if ok:
        add_message("assistant", "text", answer)
    else:
        st.error(answer)


# ---------- screens ----------

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


def show_sidebar():
    p = st.session_state.profile
    with st.sidebar:
        st.subheader("Your details")
        st.text(f"Name: {p['name']}")
        st.text(f"Email: {p['email']}")
        st.text(f"Area: {p['area']}")
        st.text(f"Authority: {p['authority_email'] or 'none (only you)'}")
        st.text(f"Tone: {p['tone']}")
        st.text(f"Language: {p['language']}")
        st.button("Start over", on_click=reset_session)


def show_chat():
    p = st.session_state.profile
    ensure_chat()
    show_sidebar()

    st.title("🏙️ CivicSnap")
    st.caption(f"Reporting for {p['area']}")

    if not st.session_state.messages:
        add_message(
            "assistant",
            "text",
            WELCOME_MESSAGE_TEMPLATE.format(name=p["name"], area=p["area"]),
        )
    else:
        for message in st.session_state.messages:
            render_message(message)

    user_input = st.chat_input(
        "Describe a civic issue or attach a photo",
        accept_file=True,
        file_type=["jpg", "jpeg", "png"],
        max_chars=1000,
    )
    handle_input(user_input)


# ---------- main ----------

init_state()

try:
    gemini_client = get_gemini_client()
except Exception:
    st.error("Gemini isn't set up. Check GEMINI_API_KEY in your secrets file.")
    st.stop()

if not st.session_state.onboarded:
    show_onboarding()
    st.stop()

show_chat()