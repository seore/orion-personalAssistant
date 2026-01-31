import subprocess
import speech_recognition as sr
import sys
import threading
import time

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

ORION_VOICE = "Karen"
ORION_RATE = "170"

_tts_engine = None
_last_spoken = None
_last_spoken_time = 0.0


def _ensure_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        import pyttsx3
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 170)

def mac_say(text: str):
    global _last_spoken, _last_spoken_time

    if not text:
        return
    
    now = time.time()
    key = text.strip()

    if key == _last_spoken and (now - _last_spoken_time) < 1.0:
        return
    
    _last_spoken = key
    _last_spoken_time = now

    def speak_thread():
        try:
            if IS_MAC:
                subprocess.Popen(["say", "-v", ORION_VOICE, "-r", ORION_RATE, text])
            elif IS_WIN:
                _ensure_tts_engine()
                _tts_engine.say(text)
                _tts_engine.runAndWait()
            else:
                print("[Orion voice]", text)
        except Exception:
          pass
    
    threading.Thread(target=speak_thread, daemon=True).start()


def listen_from_mic(timeout: float = 2.0, phrase_time_limit: float = 6.0) -> str:
    """Listen once from mic and return recognized text."""
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Listening... (speak now)", file=sys.stderr)
        recognizer.adjust_for_ambient_noise(source, duration=0.2)

        try:
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
        except sr.WaitTimeoutError:
            print("[Orion] Listening timed out while waiting for speech.", file=sys.stderr)
            return ""

    try:
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}", file=sys.stderr)
        return text
    except sr.UnknownValueError:
        print("[Orion] I didn't catch that.", file=sys.stderr)
        return ""
    except sr.RequestError as e:
        print(f"[Orion] Speech recognition error: {e}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[Orion] Unexpected STT error: {e}", file=sys.stderr)
        return ""

def speak_from_command(cmd: dict):
    """cmd example: {"intent":"say_text","args":{"text":"Hello"}}"""
    if cmd.get("intent") == "say_text":
        text = cmd.get("args", {}).get("text", "")
        mac_say(text)

