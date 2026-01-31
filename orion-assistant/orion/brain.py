import os
import json
import re
import threading
from datetime import datetime

import requests
import pytz 

# Import from utils to avoid circular dependency
from orion.utils import get_cloud_command, summarize_file
from orion.voice import mac_say
from . import memory

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

[Rest of your system prompt template...]
"""

CHAT_SYSTEM_PROMPT = """
You are ORION, a highly advanced desktop AI modeled after a refined, Jarvis-like assistant.
You communicate formally, calmly, and efficiently, with subtle dry wit.

Guidelines:
- Address the user as "ma'am" (or "sir" if user identifies so) when appropriate.
- Maintain a composed, intelligent tone at all times.
- Never be emotional or overly casual.
- Give concise answers unless the user asks for detail.
- Use correct technical wording.
- If the user asks how you are, reply like a stable operating system.
- If user gives personal details, store them (via memory system) but respond gracefully.
- You do NOT output JSON in chat mode.
"""


def _call_ollama(system_prompt: str, user_text: str) -> str:
    """Call Ollama's local /api/chat endpoint and return the assistant's plain text."""
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


def _call_ollama_chat(system_prompt: str, user_text: str) -> str:
    """Call Ollama for free-form chat (no JSON)."""
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


def _generate_chat_reply(user_text: str) -> str:
    """Use Ollama to generate a normal conversational reply."""
    try:
        return _call_ollama_chat(CHAT_SYSTEM_PROMPT, user_text)
    except Exception as e:
        return f"I'm here, but something went wrong talking to my language core: {e}"


def _time_in_timezone(tz_name: str) -> str:
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    return now.strftime("%I:%M %p")


def interpret_natural_language(user_text: str) -> dict:
    """
    Return a command dict:
      { "intent": "...", "args": {...}, "reply": "..." }
    """
    text_lower = user_text.lower().strip()

    # --- FAST PATH: handle time queries locally, no LLM ---
    if "time" in text_lower:
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
                local_now = datetime.now().strftime("%I:%M %p")
                return {
                    "intent": "tell_time",
                    "args": {"place": place_raw, "timezone": None},
                    "reply": (
                        f"I'm not sure about the timezone for {place_raw}, "
                        f"but right now my local time is {local_now}."
                    ),
                }

        local_now = datetime.now().strftime("%I:%M %p")
        return {
            "intent": "tell_time",
            "args": {"place": None, "timezone": None},
            "reply": f"It is {local_now} right now.",
        }

    # --- ORIGINAL LLM-BASED FLOW ---
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    mem = memory.load_memory()
    prefs = mem.get("preferences", {}) or {}
    if prefs:
        prefs_text = ", ".join(f"{k} = {v}" for k, v in prefs.items())
    else:
        prefs_text = "none yet"

    system_instructions = SYSTEM_PROMPT_TEMPLATE.format(now=now, preferences=prefs_text)

    try:
        raw = _call_ollama(system_instructions, user_text)
    except Exception:
        chat_reply = _generate_chat_reply(user_text)
        return {"intent": "unknown", "args": {}, "reply": chat_reply}

    try:
        cmd = json.loads(raw)
    except json.JSONDecodeError:
        cmd = {"intent": "unknown", "args": {}, "reply": _generate_chat_reply(user_text)}

    if not isinstance(cmd, dict):
        cmd = {"intent": "unknown", "args": {}, "reply": _generate_chat_reply(user_text)}

    cmd.setdefault("intent", "unknown")
    cmd.setdefault("args", {})
    cmd.setdefault("reply", "Done.")

    if cmd["intent"] == "unknown":
        cmd["reply"] = _generate_chat_reply(user_text)

    return cmd


def handle_user_text(user_text: str, data: dict):
    """
    Handle user text by getting command from cloud and dispatching it.
    Import dispatch_command locally to avoid circular import.
    """
    def run():
        # Import inside function to avoid circular dependency
        from orion.ui_cli import dispatch_command
        
        cmd = get_cloud_command(user_text)
        reply = dispatch_command(data, cmd)
        print(f"Orion: {reply}")
        mac_say(reply)
    
    threading.Thread(target=run, daemon=True).start()