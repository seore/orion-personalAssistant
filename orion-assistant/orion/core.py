import json
import os
import subprocess
import shlex

from datetime import datetime
from pathlib import Path

DATA_FILE = "data.json"

def _run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "AppleScript error")
    return result.stdout.strip()


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"notes": [], "tasks": [], "reminders": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ----- Notes -----
def add_note_macos(content: str, folder: str = "Notes") -> str:
    """
    Create a new note in the Apple Notes app.
    Uses the first line as the title.
    """
    if not content:
        return "I need some text to put in the note."

    # Basic escaping for quotes
    safe_content = content.replace('"', '\\"')
    title = safe_content.split("\n", 1)[0][:40] or "Untitled"

    script = f'''
    tell application "Notes"
        activate
        set targetAccount to default account
        set targetFolder to folder "{folder}" of targetAccount
        make new note at targetFolder with properties {{name:"{title}", body:"{safe_content}"}}
    end tell
    '''
    _run_osascript(script)
    return f"I've added a note to your Apple Notes in the '{folder}' folder."


def add_note(data, content: str) -> str:
    """
    Save note in Orion's JSON *and* in Apple Notes.
    """
    # 1) store locally (if you still want that)
    notes = data.setdefault("notes", [])
    notes.append({"content": content})
    save_data(data)

    # 2) send to macOS Notes
    try:
        mac_msg = add_note_macos(content)
    except Exception as e:
        mac_msg = f"(Couldn't update Apple Notes: {e})"

    return f"Note saved. {mac_msg}"


def list_notes(data):
    if not data["notes"]:
        return "You have no notes yet."
    lines = ["Your notes:"]
    for n in data["notes"]:
        lines.append(f"{n['id']}. ({n['created_at']}) {n['content']}")
    return "\n".join(lines)


# ----- Tasks -----

def add_task(data, description, due_iso=None):
    task = {
        "id": len(data["tasks"]) + 1,
        "description": description,
        "done": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "due": due_iso,
    }
    data["tasks"].append(task)
    save_data(data)
    return f"Task #{task['id']} added."


def list_tasks(data):
    if not data["tasks"]:
        return "You have no tasks yet."
    now = datetime.now()
    lines = ["Your tasks:"]
    for t in data["tasks"]:
        status = "done" if t["done"] else "pending"
        line = f"{t['id']}. [{status}] {t['description']}"
        if t["due"]:
            try:
                due = datetime.fromisoformat(t["due"])
                overdue = (not t["done"]) and (due < now)
                line += f" (due: {t['due']}"
                if overdue:
                    line += " - OVERDUE"
                line += ")"
            except ValueError:
                line += f" (due: {t['due']})"
        lines.append(line)
    return "\n".join(lines)


def complete_task(data, task_id: int):
    for t in data["tasks"]:
        if t["id"] == task_id:
            if t["done"]:
                return "That task is already complete."
            t["done"] = True
            save_data(data)
            return f"Task #{task_id} marked as done."
    return "I couldn't find a task with that ID."


# ----- Reminders -----
def add_reminder_macos(text: str, time_str: str | None) -> str:
    """
    Create a reminder in the macOS Reminders app.
    time_str is 'YYYY-MM-DD HH:MM' in local time, or None for no date.
    """
    if not text:
        return "I need some text for the reminder."

    safe_text = text.replace('"', '\\"')

    if time_str:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        osa_date = dt.strftime("%d %B %Y %H:%M")
        script = f'''
        tell application "Reminders"
            activate
            make new reminder with properties {{name:"{safe_text}", remind me date:date "{osa_date}"}}
        end tell
        '''
    else:
        script = f'''
        tell application "Reminders"
            activate
            make new reminder with properties {{name:"{safe_text}"}}
        end tell
        '''

    _run_osascript(script)
    if time_str:
        return f"Reminder added to Reminders for {time_str}."
    else:
        return "Reminder added to Reminders."
    

def add_reminder(data, text: str, time_str: str | None) -> str:
    """
    Save reminder in Orion's JSON *and* in macOS Reminders.
    """
    reminders = data.setdefault("reminders", [])
    reminders.append({"text": text, "time": time_str})
    save_data(data)

    try:
        mac_msg = add_reminder_macos(text, time_str)
    except Exception as e:
        mac_msg = f"(Couldn't update Reminders app: {e})"

    return f"Reminder saved. {mac_msg}"


def list_reminders(data):
    if not data["reminders"]:
        return "You have no reminders."
    lines = ["Your reminders:"]
    for r in data["reminders"]:
        status = "DONE" if r["triggered"] else "PENDING"
        lines.append(f"{r['id']}. [{status}] {r['time']} -> {r['text']}")
    return "\n".join(lines)


def get_due_reminders(data):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    due = []

    reminders = data.get("reminders", [])

    for r in reminders:
        if r.get("triggered", False):
            continue

        t = r.get("time")
        if not t:
            continue
        if t <= now_str:
            r["triggered"] = True
            due.append(r)
    save_data(data)
    return due


# ----- Files -----

def find_files_by_name(keyword, start_path=None):
    start = Path(start_path or Path.home()).expanduser()
    if not start.exists():
        return "Start path does not exist."
    matches = []
    for root, dirs, files in os.walk(start):
        for f in files:
            if keyword.lower() in f.lower():
                matches.append(os.path.join(root, f))
    if not matches:
        return f"No files found containing '{keyword}'."
    return "Matching files:\n" + "\n".join(matches)
