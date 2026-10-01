import streamlit as st
from google import genai

MODEL_NAME = "gemini-3.5-flash"

st.set_page_config(page_title="CivicSnap", page_icon="🏙️")
st.title("🏙️ CivicSnap")
st.caption("Stage 1: setup check")

st.subheader("Secrets check")
for key in ["GEMINI_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"]:
    try:
        found = key in st.secrets
    except Exception:
        found = False
    st.write(f"{'✅' if found else '❌'} {key}")

st.subheader("Gemini check")
if st.button("Test Gemini"):
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        reply = client.models.generate_content(
            model=MODEL_NAME, contents="Reply with exactly: CIVICSNAP OK"
        )
        st.success(reply.text)
    except Exception as error:
        st.error(f"Failed: {error}")