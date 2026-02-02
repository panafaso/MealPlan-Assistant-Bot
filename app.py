import re
import html
import streamlit as st
import requests

st.set_page_config(page_title="MealPlan Bot", layout="centered")

st.title("MealPlan Assistant Bot")
st.caption("Virtual Assistant")
st.markdown("Backend: Rasa + Python Actions")

RASA_URL = "http://localhost:5005/webhooks/rest/webhook"


def format_bot_text_to_html(text: str) -> str:
    """Format bot text for nicer chat bubbles (escape + compact spacing + basic lists)."""
    if not text:
        return ""

    # Escape to avoid breaking HTML
    t = html.escape(text.strip())

    # Normalize newlines
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse excessive blank lines
    t = re.sub(r"\n{3,}", "\n\n", t)

    lines = t.split("\n")
    out = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    bullet_re = re.compile(r"^\s*(?:•|-)\s+(.*)$")
    num_re = re.compile(r"^\s*(\d+)[\.\)]\s+(.*)$")

    for line in lines:
        line_stripped = line.strip()

        # Blank line -> paragraph break
        if line_stripped == "":
            close_lists()
            out.append("<br>")
            continue

        m_b = bullet_re.match(line_stripped)
        m_n = num_re.match(line_stripped)

        # Numbered list
        if m_n:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol style='margin:6px 0 6px 18px;'>")
                in_ol = True
            out.append(f"<li style='margin:2px 0;'>{m_n.group(2)}</li>")
            continue

        # Bulleted list
        if m_b:
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul style='margin:6px 0 6px 18px;'>")
                in_ul = True
            out.append(f"<li style='margin:2px 0;'>{m_b.group(1)}</li>")
            continue

        # Normal line
        close_lists()
        out.append(f"<div style='margin:2px 0;'>{line_stripped}</div>")

    close_lists()

    # Clean repeated breaks
    html_text = "\n".join(out)
    html_text = re.sub(r"(?:<br>\s*){3,}", "<br><br>", html_text)

    return html_text


# Chat history
if "chat" not in st.session_state:
    st.session_state.chat = []

# Render bubbles
for speaker, text in st.session_state.chat:
    if speaker == "You":
        st.markdown(
            f"""
            <div style="display:flex; justify-content:flex-end;">
                <div style="background:#4f7cff; color:white; padding:10px 12px;
                border-radius:15px; margin:5px 0; max-width:70%;
                line-height:1.35;">
                    {html.escape(text)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        bot_html = format_bot_text_to_html(text)
        st.markdown(
            f"""
            <div style="display:flex; justify-content:flex-start;">
                <div style="background:#eeeeee; padding:10px 12px;
                border-radius:15px; margin:5px 0; max-width:70%;
                line-height:1.35;">
                    {bot_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# Input form (prevents re-send loops)
with st.form("chat_form", clear_on_submit=True):
    msg = st.text_input("Type a message")
    send = st.form_submit_button("Send")

if send and msg.strip():
    msg = msg.strip()
    st.session_state.chat.append(("You", msg))

    try:
        st.write("Sending to:", RASA_URL)  # debug
        r = requests.post(
            RASA_URL,
            json={"sender": "user", "message": msg},
            timeout=20,
        )
        st.write("HTTP status:", r.status_code)  # debug
        r.raise_for_status()
        bot_messages = r.json()
    except Exception as e:
        st.session_state.chat.append(("Bot", f"Error talking to Rasa: {e}"))
        st.rerun()

    if not bot_messages:
        st.session_state.chat.append(("Bot", "(no response)"))
    else:
        # Merge all bot texts into one bubble
        texts = []
        for m in bot_messages:
            t = m.get("text")
            if t:
                texts.append(t.strip())

        combined = "\n".join(texts) if texts else "(no text response)"
        st.session_state.chat.append(("Bot", combined))

    st.rerun()