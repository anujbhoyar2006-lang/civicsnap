# 🏙️ CivicSnap: AI Civic Issue Reporter

Photograph a civic problem, tell the bot where it is, review the AI-drafted complaint, and email it with one click.

**Live app:** [https://civicsnap-f826gp4bspp9ujyh2gizyj.streamlit.app/](https://civicsnap-f826gp4bspp9ujyh2gizyj.streamlit.app/)

**Demo note:** this app runs on Google's free Gemini tier, which allows about 20 AI requests per day. If you see "free AI usage limit reached", the daily quota is used up. Please try again after the daily reset.

## What it does

CivicSnap helps citizens report public infrastructure problems: potholes, broken streetlights, garbage piles, open drains, water leakage and damaged public property. A user uploads a photo or describes the issue. Gemini identifies the problem, asks for the exact location (a photo can't show where it is), and drafts a structured complaint. The user edits it, confirms, and CivicSnap emails it with a Report ID and date.

## How it works

1. **Onboard once:** name, email, city or area, complaint tone (Formal or Short) and language (English, Hindi or Marathi).
2. **Chat:** send a photo, text, or both. Gemini (vision and chat) identifies the issue and its category.
3. **Location:** the bot asks for a street, landmark or building. Code also rejects vague answers like "here" or just the city name.
4. **Prepare report:** a separate, strict Gemini request returns the complaint in a fixed format. A Python parser validates it.
5. **Review:** the report appears in an editable box. Every edit is re-validated live.
6. **Confirm and send:** the user ticks a confirmation box (it un-ticks if the text changes) and presses Send Report. Gmail delivers it.

## Features

- Photo or text input, with a short description and category from Gemini
- Fixed complaint format: subject, category, urgency (AI estimate), location, description, potential risk, requested action
- Exact values come from code, not AI: **Report ID** (`CS-YYYYMMDD-XXXX`), **date and time (IST)** and reporter details
- Hindi and Marathi complaints. Field labels stay in English so the parser is reliable, and the email is sent as UTF-8
- Hazard handling: the prompt tells users to stay away and call 112, and a keyword **safety banner** in code backs it up
- Confirmation checkbox, editable draft, and "Reset to AI draft"
- Optional authority recipient (report goes To the authority, Cc the user), disabled on the public demo

## Tech stack

Python, Streamlit (UI), Google Gemini through `google-genai` (chat and vision), Gmail SMTP through Python's `smtplib` (delivery), Streamlit Community Cloud (hosting).

## Project structure

```
civicsnap/
├── app.py              # Streamlit app: onboarding, chat, editor, send
├── prompts.py          # AI persona, rules, report format (kept separate from logic)
├── report.py           # Parses and validates Gemini's complaint; location check
├── mailer.py           # Builds and sends the email (UTF-8, To/Cc, Reply-To)
├── safety.py           # Keyword hazard backstop
├── limits.py           # Shared daily email counter
├── test_report.py      # 18 tests
├── test_mailer.py      # 10 tests
├── test_safety.py      # 9 tests
├── test_limits.py      # 3 tests
├── requirements.txt
└── .streamlit/secrets.toml.example
```

## Run locally

Requires Python 3.9 or newer.

```bash
git clone https://github.com/anujbhoyar2006-lang/civicsnap.git
cd civicsnap
python -m venv venv
# Windows PowerShell:  .\venv\Scripts\Activate.ps1
# macOS/Linux:         source venv/bin/activate
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` (copy `secrets.toml.example`) and fill in real values:

| Key | What it is |
|---|---|
| `GEMINI_API_KEY` | Free key from aistudio.google.com |
| `GEMINI_MODEL` | Optional. Defaults to `gemini-3.5-flash` |
| `GMAIL_ADDRESS` | The Gmail account that sends the reports |
| `GMAIL_APP_PASSWORD` | 16-character App Password (turn on 2-Step Verification, then myaccount.google.com/apppasswords) |
| `ALLOW_AUTHORITY_EMAIL` | `"true"` shows the authority field. Default is off |

```bash
streamlit run app.py
```

`secrets.toml` is git-ignored. Never commit it.

## Run the tests

```bash
python test_report.py
python test_mailer.py
python test_safety.py
python test_limits.py
```

40 tests, none of which call Gemini or send email.

## Deploy

Push to GitHub, open share.streamlit.io, choose the repo, branch `main` and `app.py`, and paste the contents of your `secrets.toml` into **Settings → Secrets**.

## Safety, privacy and honesty

- **Drafts only.** The AI never claims a report was sent. The app confirms delivery.
- **Urgency and category are AI estimates**, labelled as such in the app and in every email.
- **No identification of people or number plates.** This is a prompt rule, so it is best-effort.
- **Prompt-injection guard:** text inside photos or messages cannot change the bot's rules.
- **Location is never guessed.** The bot must ask for it, and code rejects vague answers.
- **Abuse protection on the public demo:** the authority field is off (reports go only to the sender's own address), with a daily cap of 25 emails shared by all visitors and per-session caps of 8 chat messages, 3 reports and 2 emails.

## Known limitations

- **Free-tier quota:** about 20 Gemini requests per day on the free plan. When it runs out, the app shows a friendly message until the next day.
- **Session limits are soft.** Refreshing the page resets them. The daily email cap and the disabled authority field are the hard protections.
- **The email contains the report text only.** The photo is not attached.
- **The safety banner reads text only.** A hazard visible only in a photo relies on the prompt.
- **The reporter's email is not verified,** so someone could enter another person's address. The daily cap limits this.
- **This is a complaint drafter, not an official filing system.** It does not submit to any municipal portal.
- AI output can be wrong. The user reviews and edits every report before sending.

## Tested cases

40 automated tests cover the report parser, email builder, safety keywords and daily limits. Run them with the commands above.

## Future improvements

- Attach the photo to the email
- Detect hazards in the photo itself
- Login or email verification for reporters
- Submit directly to city complaint portals where an API exists
- A database for report history and status tracking

## Credits

Built for the AI Vision Chatbot workshop, extending its onboarding, chat and send pattern. Uses Google Gemini and Streamlit.