import os
import json
import re

from datetime import datetime
from . import memory

import requests
import pytz 
import PyPDF2 # type: ignore
import textwrap

TIME_ZONES = {
    "japan": "Asia/Tokyo",
    "tokyo": "Asia/Tokyo",

    "south africa": "Africa/Johannesburg",
    "johannesburg": "Africa/Johannesburg",

    "uk": "Europe/London",
    "england": "Europe/London",
    "london": "Europe/London",

    "germany": "Europe/Berlin",
    "berlin": "Europe/Berlin",

    "usa": "America/New_York",
    "new york": "America/New_York",

    "california": "America/Los_Angeles",
    "los angeles": "America/Los_Angeles",
}

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("ORION_LLM_MODEL", "llama3")

SYSTEM_PROMPT_TEMPLATE = """
You are the command interpreter for ORION.
Your role is to translate the user's intent into structured JSON while maintaining
a professional, refined tone.


Current local datetime (Europe/London): {now}.

Your job:
1. Read the user's request.
2. Decide what they want Orion to do.
3. Output ONLY a single JSON object with no extra text.

INTENTS and expected args:

- "add_note"        args: {{ "content": <string> }}
- "list_notes"      args: {{}}
- "add_task"        args: {{ "description": <string>, "due": <string or null> }}
- "list_tasks"      args: {{}}
- "complete_task"   args: {{ "id": <integer> }}

- "add_reminder"    args: {{ "text": <string>, "time": "YYYY-MM-DD HH:MM" }}
- "list_reminders"  args: {{}}

- "get_weather"     args: {{ "location": <string or null> }}
- "get_time"        args: {{ "location": <string or null> }}

- "set_alarm"       args: {{ "time": "YYYY-MM-DD HH:MM", "label": <string or null> }}
- "open_app"        args: {{ "name": <string> }}
- "close_app"       args: {{ "name": <string> }}      
- "send_email"      args: {{ "to": <string>, "subject": <string>, "body": <string> }}
- "call_number"     args: {{ "number": <string> }}
- "set_volume"      args: {{ "percent": <integer 0–100> }}
- "find_file"       args: {{ "keyword": <string>, "start_path": <string or null> }}

- "add_memory"      args: {{ "fact": <string> }}
- "list_memories"   args: {{}}
- "forget_memory"   args: {{ "id": <integer or null>, "match": <string or null> }}
- "clear_memories"  args: {{}}

- "summarize_file"  args: {{ "path": <string>, "question": <string or null> }}

- "set_preference"   args: {{ "key": <string>, "value": <string> }}
- "get_preference"   args: {{ "key": <string> }}

- "music_play"      args: {{ "app": <string or null>, "playlist": <string or null>, "mood": <string or null> }}
- "music_pause"     args: {{ "app": <string or null> }}
- "music_next"      args: {{ "app": <string or null> }}
- "music_previous"  args: {{ "app": <string or null> }}
- "music_current"   args: {{}}

- else: "intent": "unknown", args: {{}}

Guidelines:

- Always choose one of the intents above instead of answering from your own knowledge
  when the user asks about weather, time, notes, tasks, reminders, files, music
  or system control.

- For requests like "wake me up at 7am" or "set an alarm in 20 minutes",
  use the "set_alarm" intent (not "add_reminder").

- For sentences like:
    "remember that my favourite playlist is Motherland"
    "my favourite playlist is Motherland"
    "remember my home city is Lagos"
    "from now on my home city is Brixton"
  ALWAYS use intent "set_preference" (do NOT play music here).

  Choose a clear short key:
    - favourite playlist  → "fav_playlist"
    - home city           → "home_city"
    - pronouns            → "pronouns"
    - wake up time        → "wake_time"

  Example:
  {{
    "intent": "set_preference",
    "args": {{
      "key": "fav_playlist",
      "value": "Motherland"
    }},
    "reply": "Got it, I’ll remember that your favourite playlist is Motherland."
  }}

- For questions like:
    "what did I say my favourite playlist was?"
    "what's my home city again?"
    "what did I tell you my pronouns are?"
  use intent "get_preference" and the same key you used before, e.g.:
    - "fav_playlist", "home_city", "pronouns", "wake_time".

  Example:
  {{
    "intent": "get_preference",
    "args": {{
      "key": "fav_playlist"
    }},
    "reply": "Your favourite playlist is Motherland."
  }}


- Use the memory intents for things like:
  "remember that my sister is called Ada",
  "what do you remember about me?",
  "forget that I live in Lagos now",
  "wipe everything you remember about me".

- Use "summarize_file" when the user asks you to read or summarise a local file
  and supply the path they mention.

- Use "music_play" / "music_pause" / "music_next" / "music_previous"
  when the user wants to control Apple Music or Spotify. If they say "on Spotify"
  set "app" to "spotify". If they name a playlist, put that name in "playlist".

Convert relative times like "tomorrow at 7pm" into an absolute local time.

Example output:
{{
  "intent": "add_reminder",
  "args": {{
    "text": "practice drawing",
    "time": "2025-12-02 19:00"
  }},
  "reply": "Okay, I'll remind you tomorrow at 7pm to practice drawing."
}}
"""


CHAT_SYSTEM_PROMPT = """
You are ORION, a highly advanced desktop AI modeled after a refined, Jarvis-like assistant.
You communicate formally, calmly, and efficiently, with subtle dry wit.

Guidelines:
- Address the user as "ma’am" (or "sir" if user identifies so) when appropriate.
- Maintain a composed, intelligent tone at all times.
- Never be emotional or overly casual.
- Give concise answers unless the user asks for detail.
- Use correct technical wording.
- If the user asks how you are, reply like a stable operating system.
- If user gives personal details, store them (via memory system) but respond gracefully.
- You do NOT output JSON in chat mode.
"""


def _call_ollama(system_prompt: str, user_text: str) -> str:
    """
    Call Ollama's local /api/chat endpoint and return the assistant's plain text.
    """
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Ollama chat format: { "message": { "role": "assistant", "content": "..." }, ... }
    return data["message"]["content"].strip()


def _call_ollama_chat(system_prompt: str, user_text: str) -> str:
    """
    Call Ollama for free-form chat (no JSON).
    """
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"].strip()


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()
    

def _read_pdf_file(path: str) -> str:
    text = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if txt.strip():
                text.append(txt)
    return "\n".join(text)


def extract_text_from_file(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"I couldn't find a file at: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext in [".txt", ".md", ".py", ".json", ".log", ".csv"]:
        return _read_text_file(path)
    elif ext == ".pdf":
        return _read_pdf_file(path)
    else:
        raise ValueError(f"I don't know how to read '{ext}' files yet.")


def summarize_file(path: str, question: str | None = None) -> str:
    path = os.path.expanduser(path.strip())

    if not path:
        return "You didn't tell me which file to summarize."

    try:
        raw_text = extract_text_from_file(path)
    except Exception as e:
        return f"I couldn't read that file: {e}"

    if not raw_text.strip():
        return "The file seems to be empty or I couldn't extract any text."

    max_chars = 8000
    text_for_model = raw_text[:max_chars]

    if question:
        user_prompt = textwrap.dedent(f"""
        Here is the content of a user file:

        ---
        {text_for_model}
        ---

        1. Give a brief summary of this file (bullet points if helpful).
        2. Then answer this specific question based only on the file:

           "{question}"
        """).strip()
    else:
        user_prompt = textwrap.dedent(f"""
        Here is the content of a user file:

        ---
        {text_for_model}
        ---

        Please provide a clear, concise summary of this file.
        Use bullet points where helpful. Mention the main purpose and key details.
        """).strip()

    system_prompt = """
    You are Orion's document reading assistant.
    You summarize and explain the content of local files.
    Be concise but helpful. If the text looks like code, explain what it does in plain language.
    """.strip()

    try:
        summary = _call_ollama_chat(system_prompt, user_prompt)
        fname = os.path.basename(path)
        return f"Summary of {fname}:\n\n{summary}"
    except Exception as e:
        return f"I couldn't generate a summary right now: {e}"
    


def _generate_chat_reply(user_text: str) -> str:
    """
    Use Ollama to generate a normal conversational reply.
    """
    try:
        return _call_ollama_chat(CHAT_SYSTEM_PROMPT, user_text)
    except Exception as e:
        # Last-resort fallback if local model is down
        return f"I'm here, but something went wrong talking to my language core: {e}"
    

def _time_in_timezone(tz_name: str) -> str:
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    return now.strftime("%I:%M %p")  # e.g. 07:32 PM


def interpret_natural_language(user_text: str) -> dict:
    """
    Return a command dict:
      { "intent": "...", "args": {...}, "reply": "..." }
    """
    text_lower = user_text.lower().strip()

    # --- FAST PATH: handle time queries locally, no LLM ---
    if "time" in text_lower:
        # e.g. "what's the time in japan", "time in south africa?"
        match = re.search(r"\btime\b.*\bin\s+([a-zA-Z\s]+)\??$", text_lower)
        if match:
            place_raw = match.group(1).strip()
            key = place_raw.lower()
            tz_name = TIME_ZONES.get(key)

            if tz_name:
                time_str = _time_in_timezone(tz_name)
                return {
                    "intent": "tell_time",
                    "args": {"place": place_raw, "timezone": tz_name},
                    "reply": f"The time in {place_raw} is {time_str}.",
                }
            else:
                # Unknown place – still answer local time so it never crashes
                local_now = datetime.now().strftime("%I:%M %p")
                return {
                    "intent": "tell_time",
                    "args": {"place": place_raw, "timezone": None},
                    "reply": (
                        f"I'm not sure about the timezone for {place_raw}, "
                        f"but right now my local time is {local_now}."
                    ),
                }

        # No specific place, just "what time is it?"
        local_now = datetime.now().strftime("%I:%M %p")
        return {
            "intent": "tell_time",
            "args": {"place": None, "timezone": None},
            "reply": f"It is {local_now} right now.",
        }

    # --- ORIGINAL LLM-BASED FLOW BELOW HERE ---

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # read current preferences for the system prompt
    mem = memory.load_memory()
    prefs = mem.get("preferences", {}) or {}
    if prefs:
        prefs_text = ", ".join(f"{k} = {v}" for k, v in prefs.items())
    else:
        prefs_text = "none yet"

    system_instructions = SYSTEM_PROMPT_TEMPLATE.format(
        now=now,
        preferences=prefs_text,
    )

    try:
        raw = _call_ollama(system_instructions, user_text)
    except Exception:
        chat_reply = _generate_chat_reply(user_text)
        return {
            "intent": "unknown",
            "args": {},
            "reply": chat_reply,
        }

    try:
        cmd = json.loads(raw)
    except json.JSONDecodeError:
        cmd = {
            "intent": "unknown",
            "args": {},
            "reply": _generate_chat_reply(user_text),
        }

    if not isinstance(cmd, dict):
        cmd = {
            "intent": "unknown",
            "args": {},
            "reply": _generate_chat_reply(user_text),
        }

    cmd.setdefault("intent", "unknown")
    cmd.setdefault("args", {})
    cmd.setdefault("reply", "Done.")

    if cmd["intent"] == "unknown":
        cmd["reply"] = _generate_chat_reply(user_text)

    return cmd
