import hashlib
import re

import streamlit as st
from google import genai
from google.genai import types

from mailer import build_email, make_report_id, recipients_for, send_email
from prompts import (
    LANGUAGES,
    REPORT_REQUEST_PROMPT,
    TONES,
    WELCOME_MESSAGE_TEMPLATE,
    build_system_prompt,
)
from report import build_report_text, location_problem, parse_report
from safety import SAFETY_MESSAGE, find_hazards
from limits import DailyCounter

MODEL_NAME = "gemini-3.5-flash"
MAX_CHAT_MESSAGES = 8          # Gemini chat requests per visitor session
MAX_REPORTS = 3                # "Prepare report" presses per session
MAX_EMAILS_PER_SESSION = 2
MAX_EMAILS_PER_DAY = 25        # across all visitors


def secret_flag(name, default=False):
    """Read an optional on/off setting from secrets."""
    try:
        return str(st.secrets.get(name, default)).strip().lower() in ("1", "true", "yes")
    except Exception:
        return default


def authority_allowed():
    """Off unless ALLOW_AUTHORITY_EMAIL = "true" is set in secrets."""
    return secret_flag("ALLOW_AUTHORITY_EMAIL", False)


@st.cache_resource
def get_email_counter():
    """One counter for the whole app, shared by every visitor."""
    return DailyCounter(MAX_EMAILS_PER_DAY)

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
    """Create every session-state key once, so later stages never hit a missing key.
    (report_editor is the text box's key. It only exists while a draft is shown.)
    report_id is None until the current draft has been emailed."""
    defaults = {
        "onboarded": False,
        "profile": {},
        "chat": None,
        "messages": [],
        "report_draft": "",
        "report_id": None,
        "chat_calls": 0,
        "report_calls": 0,
        "emails_sent": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# --- report draft helpers: keep draft and editor box in step ---

def set_report(text):
    st.session_state.report_draft = text
    st.session_state.report_editor = text
    st.session_state.report_id = None  # a new draft has not been sent


def clear_report():
    st.session_state.report_draft = ""
    st.session_state.pop("report_editor", None)
    st.session_state.report_id = None


def reset_editor():
    """Button callback: put Gemini's original draft back in the box."""
    st.session_state.report_editor = st.session_state.report_draft


@st.cache_resource
def get_gemini_client():
    """Built once and reused. Streamlit reruns the script on every click, and a
    client created as a plain variable would be rebuilt and closed each time."""
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def get_gmail_credentials():
    try:
        return st.secrets["GMAIL_ADDRESS"], st.secrets["GMAIL_APP_PASSWORD"]
    except Exception:
        return None, None


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


def generate_report_text():
    """Ask Gemini for the final complaint WITHOUT touching the chat history.
    A copy of the history plus the hidden request goes in one separate call, so
    NO_LOCATION or the report never become part of the normal conversation."""
    p = st.session_state.profile
    try:
        history = st.session_state.chat.get_history(curated=True)
        request = types.Content(
            role="user", parts=[types.Part(text=REPORT_REQUEST_PROMPT)]
        )
        reply = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=list(history) + [request],
            config=types.GenerateContentConfig(
                system_instruction=build_system_prompt(
                    p["tone"], p["language"], p["area"]
                )
            ),
        )
        text = (reply.text or "").strip()
        if not text:
            return False, "Gemini returned an empty reply. Please try again."
        return True, text
    except Exception as error:
        return False, f"Something went wrong preparing the report: {error}"


def prepare_report():
    """Generate, parse and store the report draft, or explain what is missing."""
    if st.session_state.report_calls >= MAX_REPORTS:
        st.warning(
            "You've reached the report limit for this demo session. "
            "Press Start over to begin a new one."
        )
        return
    st.session_state.report_calls += 1
    with st.spinner("Preparing your report..."):
        ok, raw = generate_report_text()

    if not ok:
        st.error(raw)
        return

    result = parse_report(raw)
    status = result["status"]

    if status == "no_issue":
        clear_report()
        st.warning(
            "No civic issue has been discussed yet. "
            "Send a photo or describe the problem first."
        )
    elif status == "no_location":
        clear_report()
        st.warning(
            "I still need the exact location (a street, landmark, building or "
            "junction). Tell me in the chat, then press Prepare report again."
        )
    elif status == "malformed":
        clear_report()
        st.error(
            "Gemini's reply wasn't in the expected format, so no report was "
            "created. Please press Prepare report again."
        )
        with st.expander("What Gemini returned (for debugging)"):
            st.text(result["raw"] or "(empty)")
            st.caption(result["problem"])
    else:
        set_report(build_report_text(result["fields"]))


def send_now(fields, report_text):
    """Build and send the email. Marks the draft as sent only if Gmail accepts it."""
    sender, app_password = get_gmail_credentials()
    if not sender or not app_password:
        st.error("Email isn't set up. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD in your secrets.")
        return
    
    if st.session_state.emails_sent >= MAX_EMAILS_PER_SESSION:
        st.warning("You've reached the email limit for this demo session.")
        return
    
    if not get_email_counter().try_take():
        st.error("The demo has reached its daily email limit. Please try again tomorrow.")
        return
    
    report_id = make_report_id()
    message = build_email(
        sender,
        st.session_state.profile,
        fields["subject"],
        report_text,
        report_id,
    )
    with st.spinner("Sending your report..."):
        ok, error = send_email(message, sender, app_password)

    if ok:
        st.session_state.report_id = report_id
        st.session_state.emails_sent += 1
        st.rerun()
    else:
        st.error(error)

def show_safety_banner():
    """Code backstop for the prompt's safety rule. Reads the user's typed text
    and the report box, so it works even if Gemini forgets to warn."""
    texts = [
        m["content"]
        for m in st.session_state.messages
        if m["role"] == "user" and m["kind"] == "text"
    ]
    texts.append(st.session_state.get("report_editor", ""))
    hazards = find_hazards("\n".join(texts))
    if hazards:
        st.error(SAFETY_MESSAGE.format(hazards=", ".join(hazards)))

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
    
    if st.session_state.chat_calls >= MAX_CHAT_MESSAGES:
        st.warning(
            "You've reached the message limit for this demo session. "
            "Press Start over in the sidebar to begin a new one."
        )
        return

    # Any new message makes an existing report out of date.
    clear_report()

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
        
    st.session_state.chat_calls += 1
    with st.spinner("Looking into it..."):
        ok, answer = ask_gemini(parts)

    if ok:
        add_message("assistant", "text", answer)
        st.rerun()  # redraw so the Prepare report button updates
    else:
        st.error(answer)


def show_report_editor():
    """Editable report box + live validation + preview + confirmed send."""
    if not st.session_state.report_draft:
        return

    p = st.session_state.profile
    sent_id = st.session_state.report_id
    to_addr, cc_addr = recipients_for(p["email"], p["authority_email"])

    st.divider()
    st.subheader("📝 Review and edit your report")

    if sent_id:
        copy_note = f", with a copy to `{cc_addr}`" if cc_addr else ""
        st.success(
            f"✅ Report **{sent_id}** was emailed to `{to_addr}`{copy_note}. "
            "Check your inbox (and Spam). To report something else, chat again "
            "or press Prepare report."
        )
    else:
        st.caption(
            "Fix anything the AI got wrong. Changes apply when you press Ctrl+Enter "
            "or click outside the box. Chatting again or pressing Prepare report "
            "replaces this text with a fresh draft. Nothing is sent until you tick "
            "the confirmation box and press Send Report."
        )

    st.text_area(
        "Report text",
        key="report_editor",
        height=320,
        max_chars=12000,
        label_visibility="collapsed",
        disabled=bool(sent_id),
    )
    st.button("↩️ Reset to AI draft", on_click=reset_editor, disabled=bool(sent_id))

    result = parse_report(st.session_state.report_editor)
    status = result["status"]

    if status in ("no_issue", "no_location"):
        st.error("This text isn't a complaint. Use Reset to AI draft to restore it.")
        return
    if status == "malformed":
        st.error(
            f"This report can't be used yet. {result['problem']} "
            "Fix the text above, or use Reset to AI draft."
        )
        return

    f = result["fields"]
    problems = []
    issue = location_problem(f["location"], p["area"])
    if issue:
        problems.append(issue)

    for note in result["notes"]:
        st.info(note)
    for problem in problems:
        st.warning(problem)
        
    if find_hazards(st.session_state.report_editor) and f["urgency"] != "High":
        st.warning(
            "The report mentions a possible hazard, but the urgency is "
            f"{f['urgency']}. Consider changing the Urgency line to High (AI estimate)."
        )

    st.markdown("**Preview of what will be sent**")
    col1, col2 = st.columns(2)
    col1.markdown(f"**Category:** {f['category']}")
    col2.markdown(f"**Urgency:** {f['urgency']} (AI estimate)")
    st.markdown(f"**Subject:** {f['subject']}")
    st.markdown(f"**Location:** {f['location']}")
    st.markdown(f"**Description:** {f['description']}")
    st.markdown(f"**Potential risk:** {f['risk']}")
    st.markdown(f"**Requested action:** {f['action']}")

    if problems:
        st.error("Not ready yet. Fix the issue above in the text box.")
        return
    if sent_id:
        return

    # ---- confirmed send: only reachable with a valid, specific report ----
    st.success("✅ The report looks complete.")
    if cc_addr:
        st.info(
            f"This report will be emailed to `{to_addr}`, "
            f"with a copy to you (`{cc_addr}`)."
        )
        label = f"I have checked this report and want to email it to {to_addr}."
    else:
        st.info(f"This report will be emailed only to you (`{to_addr}`).")
        label = "I have checked this report and want to email it."

    report_text = build_report_text(f)
    # The tick belongs to this exact text: edit the report and it un-ticks itself.
    digest = hashlib.sha1(report_text.encode("utf-8")).hexdigest()[:10]
    confirmed = st.checkbox(label, key=f"confirm_{digest}")

    if st.button("📤 Send Report", disabled=not confirmed, type="primary"):
        send_now(f, report_text)


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
        if authority_allowed():
            authority_email = st.text_input(
                "Authority email (optional)",
                max_chars=100,
                placeholder="Leave blank to send the report only to yourself",
                help="If filled, the report goes to this address and you are copied.",
            )
        else:
            authority_email = ""
            st.caption(
                "Public demo: reports are emailed only to your own address. "
                "Sending to an authority is disabled here."
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

    header_col, button_col = st.columns([5, 2], vertical_alignment="center")
    with header_col:
        st.title("🏙️ CivicSnap")
    with button_col:
        has_user_message = any(m["role"] == "user" for m in st.session_state.messages)
        prepare_clicked = st.button("📝 Prepare report", disabled=not has_user_message)
    st.caption(f"Reporting for {p['area']}")
    show_safety_banner()

    if prepare_clicked:
        prepare_report()

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

    show_report_editor()

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