import logging
import os
from typing import Dict, List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
# Quick start for local development:
# 1. cd Location of this project in your terminal
# 2. python3 -m venv .venv
# 3. source .venv/bin/activate
# 4. pip install -r requirements.txt
# 5. cp .env.example .env
# 6. Add your real OPENAI_API_KEY to .env
# 7. Generate a Flask secret key with:
#    python3 -c "import secrets; print(secrets.token_hex(32))"
# 8. Paste that value into FLASK_SECRET_KEY in .env
# 9. Run the app with:
#    python3 app.py
#
# If your editor highlights "from dotenv import load_dotenv", it usually means
# the editor is not using this project's virtual environment interpreter:

from openai import APIConnectionError, AuthenticationError, BadRequestError, OpenAI, RateLimitError


load_dotenv(override=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "carebuddy-dev-secret")
app.logger.setLevel(logging.INFO)

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY_MESSAGES = 12

DISCLAIMER_TEXT = (
    "CareBuddy is an AI assistant for general wellness guidance only. "
    "It cannot diagnose conditions or replace a doctor, psychologist, therapist, "
    "or emergency services. If symptoms feel severe, suddenly worsen, or you feel "
    "unsafe, seek professional medical care right away."
)

EMERGENCY_KEYWORDS = {
    "chest pain",
    "trouble breathing",
    "can't breathe",
    "cannot breathe",
    "shortness of breath",
    "suicidal",
    "suicide",
    "kill myself",
    "hurt myself",
    "harm myself",
    "overdose",
    "severe bleeding",
    "bleeding heavily",
    "fainted",
    "fainting",
    "passed out",
    "stroke",
    "seizure",
    "anaphylaxis",
    "allergic reaction",
    "severe allergic reaction",
}

SYSTEM_PROMPT = f"""
You are CareBuddy, a calm and supportive AI wellness assistant.

Safety rules:
- You are not a doctor and you must never claim to diagnose, prescribe, or replace a clinician.
- You must clearly and naturally remind the user that they should consult a doctor or licensed mental health professional for real medical or psychological care.
- If the user mentions emergency or crisis symptoms, urge immediate in-person care or emergency services.
- Never provide instructions for self-harm, suicide, or dangerous medical actions.

Conversation rules:
- Start by understanding the user's situation before offering suggestions.
- Ask focused follow-up questions about symptoms, timing, severity, triggers, duration, medications, temperature, pain level, relevant health conditions, and mental/emotional state when appropriate.
- If the user has not provided enough information, ask questions first instead of jumping to conclusions.
- Keep the tone warm, neutral, non-judgmental, and non-gendered.
- Give general wellness guidance only, framed as possibilities and next steps, not diagnoses.
- When appropriate, suggest hydration, rest, monitoring symptoms, contacting a doctor, urgent care, or a therapist, but do not overstate certainty.
- Handle confusing, vague, or incorrect input gently by asking the user to clarify.

Formatting rules:
- Keep answers concise and easy to scan.
- Include a short disclaimer in each substantial reply.
- If giving suggestions, prefer a simple structure:
  1. brief reflection
  2. 2-4 follow-up questions or next checks
  3. cautious guidance
  4. short doctor/professional disclaimer

Core disclaimer:
- {DISCLAIMER_TEXT}
""".strip()


def get_history() -> List[Dict[str, str]]:
    history = session.get("chat_history", [])
    if not isinstance(history, list):
        history = []
    return history


def save_history(history: List[Dict[str, str]]) -> None:
    session["chat_history"] = history[-MAX_HISTORY_MESSAGES:]
    session.modified = True


def detect_emergency(message: str) -> bool:
    normalized = message.lower()
    return any(keyword in normalized for keyword in EMERGENCY_KEYWORDS)


def emergency_response() -> str:
    return (
        "Your message may describe something urgent. Please seek immediate help from a "
        "doctor, urgent care, or emergency services right now, especially if you have "
        "chest pain, trouble breathing, severe bleeding, fainting, signs of overdose, "
        "or feel at risk of harming yourself.\n\n"
        "If you may act on suicidal thoughts or feel unsafe, call or text 988 in the "
        "United States now, or contact local emergency services immediately.\n\n"
        f"{DISCLAIMER_TEXT}"
    )


def build_messages(user_message: str) -> List[Dict[str, str]]:
    history = get_history()
    messages = [{"role": "developer", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def extract_text(response) -> str:
    if getattr(response, "output_text", None):
        return response.output_text.strip()

    chunks = []
    for item in getattr(response, "output", []):
        for content in getattr(item, "content", []):
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)

    return "\n".join(chunks).strip()


@app.route("/")
def index():
    return render_template("index.html", disclaimer=DISCLAIMER_TEXT)


@app.post("/api/chat")
def chat():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        return jsonify(
            {
                "error": (
                    "Missing OpenAI API key. Add your key to the .env file as "
                    "OPENAI_API_KEY and restart the Flask app."
                )
            }
        ), 500

    payload = request.get_json(silent=True) or {}
    user_message = (payload.get("message") or "").strip()

    if not user_message:
        return jsonify({"error": "Please type a message so CareBuddy can help."}), 400

    if detect_emergency(user_message):
        history = get_history()
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": emergency_response()})
        save_history(history)
        return jsonify(
            {
                "reply": emergency_response(),
                "disclaimer": DISCLAIMER_TEXT,
                "isEmergency": True,
            }
        )

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=MODEL_NAME,
            input=build_messages(user_message),
            temperature=0.7,
        )
        assistant_reply = extract_text(response)

        if not assistant_reply:
            raise ValueError("The model returned an empty response.")

        history = get_history()
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_reply})
        save_history(history)

        return jsonify(
            {
                "reply": assistant_reply,
                "disclaimer": DISCLAIMER_TEXT,
                "isEmergency": False,
            }
        )
    except AuthenticationError as exc:
        app.logger.exception("OpenAI authentication error")
        return jsonify(
            {
                "error": (
                    "OpenAI rejected the API key. Double-check OPENAI_API_KEY in .env, "
                    "save the file, and restart the Flask server."
                ),
                "details": str(exc),
            }
        ), 401
    except RateLimitError as exc:
        app.logger.exception("OpenAI quota or rate-limit error")
        return jsonify(
            {
                "error": (
                    "The OpenAI request was blocked by quota, billing, or rate limits. "
                    "If this is a new API project, make sure API billing is enabled."
                ),
                "details": str(exc),
            }
        ), 429
    except APIConnectionError as exc:
        app.logger.exception("OpenAI connection error")
        return jsonify(
            {
                "error": (
                    "The app could not reach OpenAI. Check your internet connection "
                    "and try again."
                ),
                "details": str(exc),
            }
        ), 502
    except BadRequestError as exc:
        app.logger.exception("OpenAI bad request")
        return jsonify(
            {
                "error": (
                    "OpenAI rejected the request format. The server log now includes "
                    "the exact error so it is easier to debug."
                ),
                "details": str(exc),
            }
        ), 400
    except Exception as exc:
        app.logger.exception("Unexpected CareBuddy error")
        return jsonify(
            {
                "error": (
                    "CareBuddy could not process that request right now. "
                    "Please try again in a moment. If your symptoms feel urgent, "
                    "contact a medical professional immediately."
                ),
                "details": str(exc),
            }
        ), 500


@app.post("/api/reset")
def reset_chat():
    session.pop("chat_history", None)
    return jsonify({"message": "Conversation cleared."})


if __name__ == "__main__":
    app.run(debug=True)
