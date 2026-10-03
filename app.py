
import time
import smtplib
import ssl
import streamlit as st
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from email.message import EmailMessage
from typing import Any, Literal, TypedDict, cast
from prompts import SUMMARY_PROMPT, SYSTEM_PROMPT, WELCOME_PROMPT


class ChatMessage(TypedDict):
    role: Literal["assistant", "user"]
    kind: Literal["text", "image"]
    content: str | bytes

try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    gemini_api_key = ""

MODEL_NAME = "gemini-3.8-flash"


@st.cache_resource
def get_genai_client(api_key: str) -> genai.Client | None:
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


gemini_client = get_genai_client(gemini_api_key)


def send_email(recipient: str, name: str, summary: str) -> tuple[bool, str]:
    try:
        smtp_host = str(st.secrets["SMTP_HOST"]).strip()
        smtp_port = int(st.secrets.get("SMTP_PORT", 587))
        smtp_username = str(st.secrets["SMTP_USERNAME"]).strip()
        smtp_password = str(st.secrets["SMTP_PASSWORD"])
        sender = str(st.secrets.get("SMTP_SENDER", smtp_username)).strip()
    except Exception:
        return False, "Email is not configured. Add SMTP settings to .streamlit/secrets.toml."

    if not all((smtp_host, smtp_username, smtp_password, sender)):
        return False, "Email is not configured. Add SMTP settings to .streamlit/secrets.toml."

    message = EmailMessage()
    message["Subject"] = "Your PhotoMath solution summary"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(f"Hi {name},\n\nHere is your math summary:\n\n{summary}")

    try:
        context = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=20) as server:
                server.login(smtp_username, smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.starttls(context=context)
                server.login(smtp_username, smtp_password)
                server.send_message(message)
    except Exception as error:
        return False, f"Email delivery failed ({type(error).__name__}). Check your SMTP settings."

    return True, ""


def get_messages() -> list[ChatMessage]:
    raw_value: object = st.session_state.get("messages", [])
    if not isinstance(raw_value, list):
        raw_value = []
    raw_messages = cast(list[object], raw_value)

    messages: list[ChatMessage] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        message_data = cast(dict[str, object], item)

        role_value = message_data.get("role")
        if role_value == "assistant":
            role: Literal["assistant", "user"] = "assistant"
        elif role_value == "user":
            role = "user"
        else:
            continue

        kind_value = message_data.get("kind")
        if kind_value == "text":
            kind: Literal["text", "image"] = "text"
        elif kind_value == "image":
            kind = "image"
        else:
            continue

        content = message_data.get("content")
        if isinstance(content, (str, bytes)):
            messages.append({"role": role, "kind": kind, "content": content})

    st.session_state["messages"] = messages
    return messages


def ask_gemini(parts: list[types.Part]) -> str | None:
    chat: Any = st.session_state.get("chat")
    if chat is None:
        return None

    for attempt in range(3):
        try:
            response = chat.send_message(parts)
            return response.text or "I couldn't generate a response."
        except ServerError as error:
            if error.code != 503:
                st.error(f"Sorry, something went wrong: {error}")
                return None
            if attempt == 2:
                st.warning("Gemini is temporarily overloaded. Please wait a moment and try again.")
                return None
            time.sleep(2 ** attempt)
        except Exception as error:
            st.error(f"Sorry, something went wrong: {error}")
            return None

    return None


def render_messages(message: ChatMessage) -> None:
    with st.chat_message(message["role"]):
        if message["kind"] == "image" and isinstance(message["content"], bytes):
            st.image(message["content"])
        else:
            st.write(message["content"])


def add_message(
    role: Literal["assistant", "user"],
    kind: Literal["text", "image"],
    content: str | bytes,
) -> None:
    message: ChatMessage = {
        "role": role,
        "kind": kind,
        "content": content
    }
    messages = get_messages()
    messages.append(message)
    st.session_state["messages"] = messages
    render_messages(message)


if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

submitted = False

if not st.session_state.onboarded:
    st.title("Photomath")
    st.caption("A simple app to solve math problems using Google GenAI.")

    with st.form("onboarding_form"):
        name = st.text_input("Enter your name:")
        email = st.text_input(
            "Enter your email:",
            placeholder="example@gmail.com",
            help="We'll use this email to send you updates about the app.")

        submitted = st.form_submit_button("Submit", type="primary")

        if submitted and (not name.strip() or not email.strip()):
            st.warning("Please fill in both fields.")

    if submitted:
        if not name.strip() or not email.strip():
            st.stop()

        st.session_state.name = name
        st.session_state.email = email
        st.session_state.onboarded = True
        st.session_state.messages = []
        st.success(f"Thank you for onboarding, {name}!")
        st.balloons()

        if gemini_client is not None:
            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
            )
        else:
            st.warning("Add GEMINI_API_KEY to .streamlit/secrets.toml to enable the AI assistant.")

        st.rerun()

    st.stop()


#create a chat interface for the user to interact with the AI assistant

header_col,button_col = st.columns([1,1],vertical_alignment="center")

with header_col:
    st.title("Photomath")
    st.caption("A simple app to solve math problems using Google GenAI.")

with button_col:
    current_messages = get_messages()
    welcome_message = WELCOME_PROMPT.format(name=st.session_state.get("name", "Guest"))
    has_solution = any(
        message["role"] == "assistant" and message["content"] != welcome_message
        for message in current_messages
    )
    if st.button("Send to Email", use_container_width=True):
        if not has_solution:
            st.info("Ask a math question and wait for its solution before emailing a summary.")
        else:
            with st.spinner("Getting your solution ready..."):
                summary = ask_gemini([types.Part.from_text(text=SUMMARY_PROMPT)])
            if summary is None:
                st.warning("I couldn't create a summary to send. Please try again.")
            else:
                success, info = send_email(st.session_state.email, st.session_state.name, summary)
                if success:
                    st.success(f"Summary sent to {st.session_state.email}!")
                else:
                    st.error(f"Failed to send summary to {st.session_state.email}: {info}")

if "name" not in st.session_state:
    st.session_state.name = "Guest"

if "email" not in st.session_state:
    st.session_state.email = ""

st.caption(f"Logged in as: {st.session_state.name} - update on this email: {st.session_state.email}")

messages = get_messages()
if not messages:
    add_message("assistant", "text", WELCOME_PROMPT.format(name=st.session_state.name))
else:
    for message in messages:
        render_messages(message)

user_input = st.chat_input(
    "Ask me a math question or upload a photo of a math problem.",
    accept_file=True,
    file_type=["png", "jpg", "jpeg"],
)

if user_input:
    photo = user_input.files[0] if user_input.files else None
    text = user_input.text.strip()
    parts: list[types.Part] = []

    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))

    if text:
        add_message("user", "text", text)
        parts.append(types.Part.from_text(text=text))
    elif photo is not None:
        parts.append(types.Part.from_text(text="Solve the math problem shown in this image."))

    if parts:
        if gemini_client is None:
            st.warning("Add GEMINI_API_KEY to .streamlit/secrets.toml to enable the AI assistant.")
        else:
            with st.spinner("Generating response..."):
                answer = ask_gemini(parts)
            if answer is not None:
                add_message("assistant", "text", answer)