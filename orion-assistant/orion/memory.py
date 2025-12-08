import json
import os
import threading
from copy import deepcopy

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MEMORY_PATH = os.path.join(_BASE_DIR, "memory.json")

_lock = threading.Lock()

_DEFAULT_MEMORY = {
    "preferences": {},          
    "stats": {
        "commands_seen": 0
    }
}


def _deep_copy_default():
    return deepcopy(_DEFAULT_MEMORY)


def load_memory() -> dict:
    """
    Load memory.json from disk.
    If missing or corrupted, return a fresh default structure.
    """
    with _lock:
        try:
            with open(_MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = _deep_copy_default()
        except json.JSONDecodeError:
            data = _deep_copy_default()

        # make sure all required keys exist
        for k, v in _DEFAULT_MEMORY.items():
            data.setdefault(k, deepcopy(v))
        return data


def save_memory(mem: dict) -> None:
    """
    Persist the in-memory structure back to memory.json
    """
    with _lock:
        tmp_path = _MEMORY_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _MEMORY_PATH)


def get_pref(key: str, default=None):
    mem = load_memory()
    return mem.get("preferences", {}).get(key, default)


def set_pref(key: str, value) -> None:
    mem = load_memory()
    mem.setdefault("preferences", {})[key] = value
    save_memory(mem)


def bump_command_count() -> int:
    """
    Increment a global 'commands_seen' counter and return the new value.
    """
    mem = load_memory()
    stats = mem.setdefault("stats", {})
    stats["commands_seen"] = int(stats.get("commands_seen", 0)) + 1
    save_memory(mem)
    return stats["commands_seen"]
