import os
import subprocess
from datetime import datetime


def open_app(name: str) -> str:
    """
    Very simple app opener:
    - 'spotify' → opens Spotify if installed in PATH
    - 'chrome'  → etc.
    For more control, map app names to full paths.
    """
    if not name:
        return "Which application should I open?"

    try:
        # use 'start' to open apps on Windows
        cmd = f'start "" "{name}"'
        subprocess.Popen(cmd, shell=True)
        return f"Opening {name}."
    except Exception as e:
        return f"I couldn't open {name}: {e}"


def set_volume(percent: int) -> str:
    """
    Example using 'nircmd' (3rd party tool) to control volume.
    User must install nircmd and put it in PATH.
    """
    try:
        percent = max(0, min(100, int(percent)))
    except ValueError:
        return "That doesn't look like a valid volume level."

    # Windows volume scale: 0–65535
    vol_val = int(percent * 655.35)

    try:
        os.system(f"nircmd.exe setsysvolume {vol_val}")
        return f"Volume set to {percent}%."
    except Exception as e:
        return f"I couldn't change the volume: {e}"


def set_alarm(time_str: str) -> str:
    """
    Very rough example: creates a one-time scheduled task which shows a message.
    time_str expects 'YYYY-MM-DD HH:MM'
    """
    if not time_str:
        return "When should I set the alarm for?"

    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        time_part = dt.strftime("%H:%M")
        date_part = dt.strftime("%d/%m/%Y")  # schtasks default format (depends on locale)
    except ValueError:
        return "The alarm time format looks invalid."

    # This uses the 'msg' command as a basic popup demonstration.
    task_name = "OrionAlarm"

    cmd = (
        f'schtasks /Create /SC ONCE /TN "{task_name}" '
        f'/TR "msg * Orion alarm for {time_str}" '
        f'/ST {time_part} /SD {date_part} /F'
    )

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return f"I couldn't create the alarm: {result.stderr.strip()}"
        return f"Alarm set for {time_str} on this Windows machine."
    except Exception as e:
        return f"I couldn't set the alarm: {e}"


def send_email(to_addr: str, subject: str, body: str) -> str:
    """
    Placeholder: you could integrate Outlook or an SMTP server.
    For now, just acknowledge.
    """
    if not to_addr:
        return "Who should I send the email to?"
    return (
        "Email integration for Windows isn't implemented yet, "
        "but I registered your intent to email "
        f"{to_addr} with subject '{subject}'."
    )


def call_number(number: str) -> str:
    """
    On Windows you might integrate with Skype, WhatsApp, or a VoIP client.
    For now, just acknowledge.
    """
    if not number:
        return "Which number should I call?"
    return f"I don't have a calling app wired up on Windows yet, but noted: {number}."
