# CareBuddy

CareBuddy is a Flask-based wellness assistant with a soft, minimal web interface. It offers general symptom and emotional wellness guidance, asks follow-up questions before giving suggestions, stores conversation context in the browser session, and shows strong medical disclaimers throughout the experience.

## Features

- Separate HTML, CSS, JavaScript, and Python files
- Friendly, neutral UI with visible safety messaging
- Flask API connected to OpenAI
- Browser-session chat memory with no database required
- Emergency keyword detection for urgent medical or crisis language
- Graceful handling for missing input and API errors

## Project structure

```text
CareBuddy/
├── app.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── styles.css
    └── js/
        └── app.js
```

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add your OpenAI key to `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
FLASK_SECRET_KEY=replace-this-with-a-random-secret
```

For `FLASK_SECRET_KEY`, use any long random string. A good way to generate one is:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Run the app

```bash
python3 app.py
```

Then open this in your browser:

```text
http://127.0.0.1:5000
```

## How the AI is configured

- The backend uses the OpenAI Python SDK and the Responses API.
- The default model in this starter is `gpt-4o-mini`, but you can change `OPENAI_MODEL` in `.env`.
- The system prompt tells CareBuddy to:
  - ask follow-up questions before giving guidance
  - avoid diagnosis
  - encourage medical or mental health professional support
  - warn on urgent symptoms
  - handle vague input gently

## Troubleshooting

- If `from dotenv import load_dotenv` is marked as an error in your editor, the editor is probably using the wrong Python interpreter. Switch it to `.venv/bin/python`.
- If the API responds with a quota, billing, or rate-limit error, the API project tied to your key may not have billing enabled yet.
- If you change `.env`, restart the Flask server so the latest values are loaded.

## Important safety note

CareBuddy is not a doctor or therapist. It provides general information only and should never replace real medical or psychological care. If someone is in danger, has severe symptoms, or may harm themselves, they should contact emergency services or a licensed professional immediately.
