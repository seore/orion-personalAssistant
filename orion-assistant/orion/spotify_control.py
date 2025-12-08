import os
import textwrap
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth


# scopes we need:
SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing"

DATA_DIR = os.path.join(os.path.expanduser("~"), ".orion")
TOKEN_CACHE = os.path.join(DATA_DIR, "spotify_token.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _get_spotify_client() -> spotipy.Spotify:
    """
    Return an authenticated Spotify client.
    On first run it will open a browser window so you can authorize Orion.
    """
    _ensure_dir()

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

    if not client_id or not client_secret:
        raise RuntimeError(
            "SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET is not set in your environment."
        )

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_path=TOKEN_CACHE,
        open_browser=True,
        show_dialog=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def _ensure_active_device(sp: spotipy.Spotify) -> Optional[str]:
    """
    Ensure there is an active device to control.
    Returns device id or None if nothing is active.
    """
    devices = sp.devices().get("devices", [])
    if not devices:
        return None

    # prefer currently active device
    for d in devices:
        if d.get("is_active"):
            return d.get("id")

    # else just take the first
    return devices[0].get("id")


def play_playlist_by_name(name: str) -> str:
    """
    Find a user's playlist by (approximate) name and start playback.
    """
    name = name.strip()
    if not name:
        return "You didn't tell me which playlist to play."

    try:
        sp = _get_spotify_client()
    except Exception as e:
        return f"I can't talk to Spotify yet: {e}"

    device_id = _ensure_active_device(sp)
    if not device_id:
        return "I couldn't find an active Spotify device. Open Spotify on your Mac or phone and try again."

    # 1) Search through user's playlists
    matched = None
    limit = 50
    offset = 0

    while True:
        playlists = sp.current_user_playlists(limit=limit, offset=offset)
        items = playlists.get("items", [])
        if not items:
            break

        for pl in items:
            pl_name = pl.get("name", "")
            if pl_name.lower() == name.lower():
                matched = pl
                break
        if matched:
            break

        if playlists.get("next"):
            offset += limit
        else:
            break

    # 2) If no exact match, try a looser match
    if not matched:
        # simple contains match
        offset = 0
        while True:
            playlists = sp.current_user_playlists(limit=limit, offset=offset)
            items = playlists.get("items", [])
            if not items:
                break

            for pl in items:
                pl_name = pl.get("name", "")
                if name.lower() in pl_name.lower():
                    matched = pl
                    break
            if matched:
                break

            if playlists.get("next"):
                offset += limit
            else:
                break

    if not matched:
        return f"I couldn't find a playlist called '{name}' in your Spotify account."

    uri = matched.get("uri")
    display_name = matched.get("name", name)

    try:
        sp.start_playback(device_id=device_id, context_uri=uri)
        return f"Playing your Spotify playlist '{display_name}'."
    except Exception as e:
        return f"I found the playlist '{display_name}', but couldn't start playback: {e}"


def resume_playback() -> str:
    try:
        sp = _get_spotify_client()
    except Exception as e:
        return f"I can't talk to Spotify yet: {e}"

    device_id = _ensure_active_device(sp)
    if not device_id:
        return "I couldn't find an active Spotify device. Open Spotify on your Mac or phone and try again."

    try:
        sp.start_playback(device_id=device_id)
        return "Resuming Spotify playback."
    except Exception as e:
        return f"I couldn't resume playback: {e}"


def pause_playback() -> str:
    try:
        sp = _get_spotify_client()
    except Exception as e:
        return f"I can't talk to Spotify yet: {e}"

    device_id = _ensure_active_device(sp)
    if not device_id:
        return "I couldn't find an active Spotify device."

    try:
        sp.pause_playback(device_id=device_id)
        return "Paused Spotify."
    except Exception as e:
        return f"I couldn't pause Spotify: {e}"


def next_track() -> str:
    try:
        sp = _get_spotify_client()
    except Exception as e:
        return f"I can't talk to Spotify yet: {e}"

    device_id = _ensure_active_device(sp)
    if not device_id:
        return "I couldn't find an active Spotify device."

    try:
        sp.next_track(device_id=device_id)
        return "Skipping to the next track in Spotify."
    except Exception as e:
        return f"I couldn't skip the track: {e}"


def previous_track() -> str:
    try:
        sp = _get_spotify_client()
    except Exception as e:
        return f"I can't talk to Spotify yet: {e}"

    device_id = _ensure_active_device(sp)
    if not device_id:
        return "I couldn't find an active Spotify device."

    try:
        sp.previous_track(device_id=device_id)
        return "Going back to the previous track in Spotify."
    except Exception as e:
        return f"I couldn't go back to the previous track: {e}"


def current_track_info() -> str:
    """
    Describe what is currently playing on Spotify.
    """
    try:
        sp = _get_spotify_client()
    except Exception as e:
        return f"I can't talk to Spotify yet: {e}"

    try:
        current = sp.current_playback()
    except Exception as e:
        return f"I couldn't read what's playing: {e}"

    if not current or not current.get("item"):
        return "Nothing seems to be playing right now on Spotify."

    item = current["item"]
    name = item.get("name", "Unknown track")
    artists = ", ".join(a["name"] for a in item.get("artists", [])) or "Unknown artist"
    album = item.get("album", {}).get("name", "Unknown album")

    return f"You're listening to '{name}' by {artists}, from the album '{album}'."
