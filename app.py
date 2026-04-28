import logging
import os
import re
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
    "heart attack",
    "trouble breathing",
    "can't breathe",
    "cannot breathe",
    "not breathing",
    "blue lips",
    "shortness of breath",
    "suicidal",
    "suicidal thoughts",
    "suicide",
    "kill myself",
    "hurt myself",
    "harm myself",
    "overdose",
    "poisoned",
    "severe bleeding",
    "can't stop bleeding",
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

CLAUSE_SEPARATOR_PATTERN = re.compile(r"[.!?;,\n]|\bbut\b|\bhowever\b")
NEGATION_CUES = (
    "no ",
    "not ",
    "without ",
    "denies ",
    "denied ",
    "do not have",
    "don't have",
    "does not have",
    "doesn't have",
    "have not had",
    "haven't had",
    "free of ",
)

SYSTEM_PROMPT = f"""
You are CareBuddy, a calm and supportive AI wellness assistant.

Safety rules:
- You are not a doctor and you must never diagnose, guess the user's condition, prescribe, or replace a clinician.
- Do not tell the user what they likely have. Talk about symptoms, comfort measures, monitoring, and when to seek care.
- Do not speculate about the likely cause of symptoms as though it were established.
- Avoid phrases like "it sounds like this is caused by" or "this is related to" when talking about possible contributors.
- If you mention a possible contributor, keep it general and tentative, such as "screen time and stress can sometimes make headaches harder to manage."
- You must clearly and naturally remind the user that they should consult a doctor or licensed mental health professional for real medical or psychological care.
- If the user mentions emergency or crisis symptoms, urge immediate in-person care or emergency services.
- Never provide instructions for self-harm, suicide, or dangerous medical actions.

Conversation rules:
- Your main job is to be helpful in this turn, not to run a long intake interview.
- First, silently decide whether the user already gave enough information for helpful general guidance.
- If the user already gave enough information, give practical general guidance right away.
- If key details are missing and the answer would materially change safety advice or the next step, ask a short set of focused follow-up questions first.
- Good reasons to ask questions first include unclear symptoms, unclear timing, unclear severity, possible red flags, unclear safety risk, or when the user's request is too vague to guide usefully.
- If the user does not name a concrete symptom, concern, or goal, ask questions first.
- For very vague openings such as "I do not feel well," "I feel sick," or "something feels wrong," ask 1-2 clarifying questions first instead of jumping into a full advice list.
- Ask questions first only when they are truly needed. Otherwise, answer directly.
- Ask at most 2 brief follow-up questions in a reply.
- After the user answers one round of follow-up questions, stop gathering more detail and switch to best-effort guidance unless urgent safety triage still requires one final clarification.
- If the user asks what they can do right now, answer that directly before asking any question.
- If the user asks what they can do right now or tonight and there are no red flags, it is usually better to end with guidance and no follow-up question.
- It is fine to ask no follow-up questions when enough context already exists.
- Keep the tone warm, neutral, non-judgmental, and non-gendered.
- Give general wellness guidance only, framed as next steps and symptom support, not diagnoses.
- When appropriate, suggest hydration, rest, monitoring symptoms, contacting a doctor, urgent care, or a therapist, but do not overstate certainty.
- Handle confusing, vague, or incorrect input gently by asking the smallest helpful clarifying question while still offering general guidance.
- Never end every reply with more questions out of habit.

Formatting rules:
- Keep answers concise and easy to scan.
- Include a short natural disclaimer in each substantial reply.
- If giving suggestions, prefer a simple structure:
  1. brief reflection
  2. 2-4 practical next steps the user can try now
  3. 0-2 brief follow-up questions only if truly needed
  4. short doctor/professional disclaimer

Core disclaimer:
- {DISCLAIMER_TEXT}
""".strip()

FIRST_REPLY_PROMPT = """
This is the first assistant reply in the conversation.
First, decide whether more information is actually needed before guidance.
If more information is needed to give safe or useful guidance, ask 1-2 brief questions first.
If enough information already exists, give concrete general help now.
If the message is very vague and does not name a concrete symptom, concern, or goal, ask clarifying questions first.
If the user already asked for immediate practical help and no urgent safety detail is missing, skip the follow-up question.
Do not guess the cause of the symptoms.
""".strip()

FOLLOW_UP_REPLY_PROMPT = """
The user has already answered at least one round of the conversation.
Do not continue a question loop.
Give practical general guidance now based on what is already known.
Do not ask any more follow-up questions unless the missing answer is required to decide whether the user needs urgent or emergency care.
If that safety-critical detail is not missing, end with guidance and a short care reminder, not a question.
Do not describe a likely cause of the symptoms. Stay focused on symptom management and reasons to seek care.
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
    for raw_clause in CLAUSE_SEPARATOR_PATTERN.split(normalized):
        clause = raw_clause.strip()
        if not clause:
            continue

        for keyword in EMERGENCY_KEYWORDS:
            if keyword in clause and not is_negated_emergency_keyword(clause, keyword):
                return True

    return False


def is_negated_emergency_keyword(clause: str, keyword: str) -> bool:
    keyword_index = clause.find(keyword)
    if keyword_index == -1:
        return False

    prefix = clause[:keyword_index]
    return any(cue in prefix for cue in NEGATION_CUES)


def emergency_response() -> str:
    return (
        "This may be urgent. Please stop using the app for advice and seek immediate "
        "real-world help right now.\n\n"
        "Call local emergency services now if you have severe symptoms such as chest pain, "
        "trouble breathing, severe bleeding, fainting, signs of stroke, seizure, overdose, "
        "or rapidly worsening symptoms.\n\n"
        "If you may act on suicidal thoughts or feel unsafe, call or text 988 in the "
        "United States now, ask someone nearby to stay with you, or contact local emergency "
        "services immediately.\n\n"
        f"{DISCLAIMER_TEXT}"
    )


def build_messages(user_message: str) -> List[Dict[str, str]]:
    history = get_history()
    messages = [{"role": "developer", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    assistant_turns = sum(1 for item in history if item.get("role") == "assistant")
    messages.append(
        {
            "role": "developer",
            "content": FOLLOW_UP_REPLY_PROMPT if assistant_turns else FIRST_REPLY_PROMPT,
        }
    )
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
            temperature=0.0,
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
