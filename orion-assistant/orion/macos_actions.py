import os
import subprocess

def run_applescript(script: str) -> str:
    out = subprocess.check_output(["osascript", "-e", script])
    return out.decode().strip()

# ---------- Reminders ----------
def create_reminder(text: str, date: str | None = None) -> str:
    if date:
        script = f'''
        tell application "Reminders"
            make new reminder with properties {{name:"{text}", remind me date:date "{date}"}}
        end tell
        '''
    else:
        script = f'''
        tell application "Reminders"
            make new reminder with properties {{name:"{text}"}}
        end tell
        '''
    run_applescript(script)
    return f"Reminder set: {text}"

# ---------- Notes ----------
def create_note(title: str, body: str = "") -> str:
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            make new note with properties {{name:"{title}", body:"{body}"}}
        end tell
    end tell
    '''
    run_applescript(script)
    return f"Note created: {title}"

# ---------- Alarm via Calendar ----------
def set_alarm(time_string: str, label: str | None = None) -> str:
    """
    Use Reminders as an 'alarm' backend.
    This will create a reminder with a due date, which will notify at that time.
    """
    if not label:
        label = "Alarm"

    return create_reminder(label, time_string)

# ---------- Volume ----------
def set_volume(percent: int) -> str:
    script = f"set volume output volume {percent}"
    run_applescript(script)
    return f"Volume set to {percent}%"

# ---------- Email ----------
def send_email(to_address: str, subject: str, body: str) -> str:
    script = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}", visible:false}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{to_address}"}}
            send
        end tell
    end tell
    '''
    run_applescript(script)
    return f"Email sent to {to_address}"

# ---------- Call via FaceTime ----------
def call_number(number: str) -> str:
    script = f'''
    tell application "FaceTime"
        activate
        call "{number}"
    end tell
    '''
    run_applescript(script)
    return f"Calling {number}..."

# -------- MUSIC CONTROL --------
def _music_app_from_arg(app: str | None) -> str:
    """
    Decide which player to control.
    - default: Apple Music ("Music")
    - if user/LLM says 'spotify' in app name → use Spotify
    """
    if not app:
        return "Music"

    a = app.lower()
    if "spot" in a:
        return "Spotify"
    if "music" in a or "apple" in a:
        return "Music"
    return "Music"


def music_play(app: str | None = None, playlist: str | None = None, mood: str | None = None) -> str:
    """
    Play music. If playlist is given and using Apple Music, try to play that playlist.
    For Spotify we currently just resume playback (no playlist-by-name).
    """
    app_name = _music_app_from_arg(app)

    # Apple Music with playlist
    if app_name == "Music" and playlist:
        script = f'''
        tell application "Music"
            activate
            try
                set targetPlaylist to playlist "{playlist}"
                play targetPlaylist
            on error
                play
            end try
        end tell
        '''
        run_applescript(script)
        return f"Playing playlist '{playlist}' in Apple Music."

    # Spotify – for now, just resume playback
    if app_name == "Spotify":
        script = '''
        tell application "Spotify"
            activate
            play
        end tell
        '''
        run_applescript(script)
        if playlist:
            return f"Playing music in Spotify (I couldn't target the playlist '{playlist}' directly)."
        return "Playing music in Spotify."

    # Default: Apple Music resume
    script = '''
    tell application "Music"
        activate
        play
    end tell
    '''
    run_applescript(script)
    return "Playing music in Apple Music."


def music_pause(app: str | None = None) -> str:
    """
    Pause music in the chosen app.
    """
    app_name = _music_app_from_arg(app)

    if app_name == "Spotify":
        script = '''
        tell application "Spotify"
            pause
        end tell
        '''
        run_applescript(script)
        return "Paused Spotify."

    script = '''
    tell application "Music"
        pause
    end tell
    '''
    run_applescript(script)
    return "Paused Apple Music."


def music_next(app: str | None = None) -> str:
    """
    Skip to the next track.
    """
    app_name = _music_app_from_arg(app)

    if app_name == "Spotify":
        script = '''
        tell application "Spotify"
            next track
        end tell
        '''
        run_applescript(script)
        return "Skipping to the next track in Spotify."

    script = '''
    tell application "Music"
        next track
    end tell
    '''
    run_applescript(script)
    return "Skipping to the next track in Apple Music."


def music_previous(app: str | None = None) -> str:
    """
    Go back to the previous track.
    """
    app_name = _music_app_from_arg(app)

    if app_name == "Spotify":
        script = '''
        tell application "Spotify"
            previous track
        end tell
        '''
        run_applescript(script)
        return "Going back to the previous track in Spotify."

    script = '''
    tell application "Music"
        previous track
    end tell
    '''
    run_applescript(script)
    return "Going back to the previous track in Apple Music."


# ---------- Open and Close App ----------
def open_app(app_name: str) -> str:
    script = f'''
    tell application "{app_name}"
        activate
    end tell
    '''
    run_applescript(script)
    return f"Opening {app_name}"


def close_app(name: str):
    if not name:
        return "Which app should I close?"
    
    script = f'''
        tell application "{name}"
            if it is running then
                quit
            end if
        end tell
    '''

    try:
        subprocess.run(["osascript", "-e", script], check=True)
        return f"Closing {name}."
    except subprocess.CalledProcessError as e:
        return f"I could not close {name}: {e}"

