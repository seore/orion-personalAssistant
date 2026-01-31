import json
import time
import traceback

from orion.core import load_data
from orion.utils import get_cloud_command
from orion.ui_cli import dispatch_command
from orion.voice import listen_from_mic, mac_say

WAKE_WORD = "orion"       
WAKE_PHRASE = "hey orion" 
SESSION_TIMEOUT = 0.0    


def normalize(text: str) -> str:
    return "".join(
        c.lower() if c.isalnum() or c.isspace() else " " for c in text
    )


def send(msg: dict):
    print(json.dumps(msg), flush=True)


def extract_command_text(text: str) -> str:
    """
    Strip wake words/phrase and return just the command part.

    Supports:
      - "hey orion, what's the weather"
      - "orion what's the weather"
      - "hey orion open spotify"
    """
    norm = normalize(text)
    lower = norm.lower().strip()

    # Full phrase first: "hey orion ..."
    if WAKE_PHRASE in lower:
        after = lower.split(WAKE_PHRASE, 1)[1].strip()
        return after

    # Single word "orion ..." anywhere
    tokens = lower.split()
    if WAKE_WORD not in tokens:
        return ""

    idx = tokens.index(WAKE_WORD)
    command_tokens = tokens[idx + 1 :]
    return " ".join(command_tokens).strip()


def has_wake_word(text: str) -> bool:
    norm = normalize(text)
    tokens = norm.split()
    if WAKE_WORD in tokens:
        return True
    if WAKE_PHRASE in norm:
        return True
    return False


def main():
    data = load_data()

    send({"type": "daemon", "state": "started"})

    intro = "System online. All subsystems functioning within optimal parameters."
    send({"type": "reply", "text": intro})
    mac_say(intro)

    session_active = False
    last_interaction = 0.0

    while True:
        # UI: we’re listening for speech
        send({"type": "status", "state": "listening"})

        # Wait for the user to speak
        text = listen_from_mic(timeout=4.0, phrase_time_limit=7.0)
        now = time.time()

        # --- No speech detected ---
        if not text:
            if session_active and (now - last_interaction) > SESSION_TIMEOUT:
                session_active = False
                send({"type": "status", "state": "idle"})
            continue

        # We heard something
        send({"type": "transcript", "text": text})

        # --- If session is NOT active, we require the wake word/phrase ---
        if not session_active:
            if not has_wake_word(text):
                # Not addressed to Orion → ignore
                send({"type": "ignore", "reason": "no_wake_word"})
                continue

            # Wake phrase present → start a session
            session_active = True
            last_interaction = now

            # Try to extract command part after "Orion"
            command_text = extract_command_text(text)

            if not command_text:
                # Just "Hey Orion" with no command
                reply = "Yes, sir?"
                send({"type": "reply", "text": reply})
                mac_say(reply)
                # stay in session; next utterance becomes the command
                continue

            # Wake + command in same sentence: "Hey Orion, open Spotify"
            send({"type": "status", "state": "processing", "text": command_text})

            try:
                cmd = get_cloud_command(command_text)
                reply = dispatch_command(data, cmd)
            except Exception as e:
                traceback.print_exc()
                reply = f"Something went wrong while processing your request: {e}"

            send({"type": "reply", "text": reply})
            mac_say(reply)
            last_interaction = now
            # remain in active session for follow-ups
            continue

        # --- Session IS active → treat any speech as a command ---

        # If too long since last interaction, drop back to idle
        if (now - last_interaction) > SESSION_TIMEOUT:
            session_active = False
            send({"type": "status", "state": "idle"})
            continue

        # We are within the session timeout: this is a follow-up command
        last_interaction = now
        send({"type": "status", "state": "processing"})

        try:
            cmd = get_cloud_command(text)
            reply = dispatch_command(data, cmd)
        except Exception as e:
            traceback.print_exc()
            reply = f"Something went wrong while processing your request: {e}"

        send({"type": "reply", "text": reply})
        mac_say(reply)


if __name__ == "__main__":
    main()
