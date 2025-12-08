import subprocess
import threading
import time
from .core import get_due_reminders


def mac_notify(title: str, text: str):
    script = f'display notification {text!r} with title {title!r}'
    subprocess.run(["osascript", "-e", script])


def reminder_loop(data, lock, stop_event):
    from .voice import mac_say  # avoid circular imports

    while not stop_event.is_set():
        with lock:
            due = get_due_reminders(data)
        for r in due:
            msg = f"Reminder: {r['text']} (set for {r['time']})"
            print(f"\n🔔 {msg}")
            mac_notify("Orion Reminder", msg)
            mac_say(msg)
        for _ in range(30):
            if stop_event.is_set():
                break
            time.sleep(1)


def start_reminder_thread(data, lock):
    stop_event = threading.Event()
    t = threading.Thread(target=reminder_loop, args=(data, lock, stop_event), daemon=True)
    t.start()
    return stop_event, t
