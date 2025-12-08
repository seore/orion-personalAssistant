import threading
import requests
import zoneinfo
import os
import sys
from datetime import datetime

from . import core
from . import memory
from .brain import interpret_natural_language, summarize_file
from .voice import listen_from_mic, mac_say
from .reminders import start_reminder_thread
from .core import get_due_reminders
from . import macos_actions  
from . import windows_actions
from . import spotify_control

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

if IS_MAC:
    sys_actions = macos_actions
elif IS_WIN:
    sys_actions = windows_actions
else: sys_actions = macos_actions

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")


# ---------- WEATHER ----------
def get_weather_text(location: str | None = None) -> str:
    if not WEATHER_API_KEY:
        return "I don't have a weather API key configured."

    try:
        if location:
            query = location
        else:
            query = "auto:ip"

        url = (
            "https://api.weatherapi.com/v1/current.json"
            f"?key={WEATHER_API_KEY}&q={requests.utils.quote(query)}"
        )

        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()

        if "error" in data:
            return f"I couldn't get the weather for {query}: {data['error']['message']}"

        loc = data["location"]
        cur = data["current"]

        city = loc["name"]
        country = loc["country"]
        temp = round(cur["temp_c"])
        cond = cur["condition"]["text"]
        feels = round(cur["feelslike_c"])
        humidity = cur["humidity"]
        wind_kph = cur["wind_kph"]
        wind_ms = wind_kph / 3.6

        return (
            f"In {city}, {country} it's {temp}°C and {cond}. "
            f"It feels like {feels}°C, humidity is {humidity}% "
            f"and wind is {wind_ms:.1f} m/s."
        )
    except Exception as e:
        return f"I couldn't fetch the weather right now: {e}"


# ---------- TIME ----------
def get_time_text(location: str | None = None) -> str:
    """
    If location is None → use system local time.
    If location is given → best-effort lookup via worldtimeapi.
    """
    try:
        if not location:
            now = datetime.now()
            return now.strftime("It's %H:%M on %A, %d %B %Y.")

        # For remote locations, use worldtimeapi (free)
        url = "https://worldtimeapi.org/api/timezone"
        res = requests.get(url, timeout=8)
        res.raise_for_status()
        zones = res.json()  # list of tz strings

        loc_lower = location.lower()
        match = None
        for z in zones:
            if loc_lower in z.lower():
                match = z
                break

        if not match:
            return f"I'm not sure what timezone '{location}' is in."

        res = requests.get(f"https://worldtimeapi.org/api/timezone/{match}", timeout=8)
        res.raise_for_status()
        data = res.json()

        dt = datetime.fromisoformat(data["datetime"].replace("Z", "+00:00"))
        local_str = dt.strftime("%H:%M on %A, %d %B %Y")
        return f"In {location} it's {local_str}."

    except Exception as e:
        return f"I couldn't get the current time: {e}"


# ---------- DISPATCH ----------
def dispatch_command(data, cmd):
    intent = cmd.get("intent", "unknown")
    args = cmd.get("args", {}) or {}
    reply = cmd.get("reply", "")

    memory.bump_command_count()

    try:
        # NOTES → macOS Notes
        if intent == "add_note":
            content = args.get("content", "")
            title = (content[:40] or "Note").strip()
            r = sys_actions.create_note(title=title, body=content)
            return reply or r

        elif intent == "list_notes":
            return core.list_notes(data)

        # TASKS GENERATION
        elif intent == "add_task":
            r = core.add_task(data, args.get("description", ""), args.get("due"))
            return reply or r

        elif intent == "list_tasks":
            return core.list_tasks(data)

        elif intent == "complete_task":
            r = core.complete_task(data, int(args["id"]))
            return reply or r
        
        elif intent == "summarize_file":
            path = args.get("path", "")
            question = args.get("question")
            return summarize_file(path, question)
        
        # MUSIC CONTROL 
        elif intent == "music_play":
            app = args.get("app")
            playlist = args.get("playlist")
            mood = args.get("mood")  

            if app and "spot" in app:
                if playlist:
                    return spotify_control.play_playlist_by_name(playlist)
                else:
                    return spotify_control.resume_playback()
            else: 
                return sys_actions.music_play(app=app or None, playlist=playlist, mood=mood)

        elif intent == "music_pause":
            app = (args.get("app") or "").lower()
            if "spot" in app:
                return spotify_control.pause_playback()
            else:
                return sys_actions.music_pause(app=app)

        elif intent == "music_next":
            app = (args.get("app") or "").lower()
            if "spot" in app:
                return spotify_control.next_track()
            else:
                return sys_actions.music_next(app=app or None)

        elif intent == "music_previous":
            app = (args.get("app") or "").lower()
            if "spot" in app:
                return spotify_control.previous_track()
            else:
                return sys_actions.music_previous(app=app)
            
        elif intent == "music_current":
            return spotify_control.current_track_info()

        # REMINDERS → macOS Reminders
        elif intent == "add_reminder":
            text = args.get("text", "")
            time_str = args.get("time")
            r = sys_actions.create_reminder(text, time_str)
            return reply or r

        elif intent == "list_reminders":
            return core.list_reminders(data)  

        # FILE SEARCH 
        elif intent == "find_file":
            r = core.find_files_by_name(args.get("keyword", ""), args.get("start_path"))
            return r

        elif intent == "set_alarm":
            time_str = args.get("time", "")
            return sys_actions.set_alarm(time_str)
        
        # MEMORY
        elif intent == "set_preference":
            key = args.get("key")
            value = args.get("value")
            if not key or value is None:
                return "What should I remember?"
            memory.set_pref(key, value)
            return reply or f"Got it, I’ll remember that your {key} is {value}."

        elif intent == "get_preference":
            key = args.get("key")
            if not key:
                return "Which preference do you want me to recall?"
            val = memory.get_pref(key)
            if val is None:
                return f"I don’t have anything saved for {key} yet."
            return reply or f"You told me your {key} is {val}."
        
        # APP LAUNCH AND CLOSE 
        elif intent == "open_app":
            app_name = args.get("name") or args.get("app") or "Safari"
            return sys_actions.open_app(app_name)
        
        elif intent == "close_app":
            app_name = args.get("name")
            return sys_actions.close_app(app_name)

        # EMAIL
        elif intent == "send_email":
            to_addr = args.get("to")
            subject = args.get("subject", "")
            body = args.get("body", "")
            return sys_actions.send_email(to_addr, subject, body)

        # PHONE CALL (FaceTime)
        elif intent == "call_number":
            number = args.get("number")
            return sys_actions.call_number(number)

        # VOLUME
        elif intent == "set_volume":
            vol = int(args.get("percent", 50))
            return sys_actions.set_volume(vol)

        # TIME
        elif intent == "get_time":
            loc = args.get("location")
            return get_time_text(loc)

        # WEATHER
        elif intent == "get_weather":
            loc = args.get("location")
            return get_weather_text(loc)

        else:
            return reply or "I'm not sure how to do that yet."
    except Exception as e:
        return f"Something went wrong executing the command: {e}"


# ---------- CLI LOOP (unchanged except it uses dispatch_command) ----------
def run_cli():
    print("=== Orion (macOS) ===")
    print("Natural language, voice, reminders with notifications.")
    print("  - Press ENTER on empty line to speak")
    print("  - Or type a request ")
    print("  - Type 'quit' or 'exit' to stop.\n")

    data = core.load_data()
    lock = threading.Lock()
    stop_event, thread = start_reminder_thread(data, lock)

    try:
        while True:
            user_text = input("You (blank = talk): ").strip()
            if user_text.lower() in ("quit", "exit"):
                break

            if not user_text:
                spoken = listen_from_mic()
                if not spoken:
                    continue
                user_text = spoken

            # catch new due reminders immediately (internal ones)
            with lock:
                due = get_due_reminders(data)
            for r in due:
                msg = f"Reminder: {r['text']} (set for {r['time']})"
                print(f"\n🔔 {msg}")
                mac_say(msg)

            print("[Orion] Thinking...")
            cmd = interpret_natural_language(user_text)

            with lock:
                reply = dispatch_command(data, cmd)

            print(f"Orion: {reply}")
            mac_say(reply)

    except KeyboardInterrupt:
        print("\n[Orion] Stopping...")
    finally:
        stop_event.set()
        thread.join(timeout=1)
        print("[Orion] Goodbye.")
