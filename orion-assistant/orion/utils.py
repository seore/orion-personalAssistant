"""
orion/utils.py - Shared utilities to avoid circular imports
"""

import os
import json
import requests
import PyPDF2
import textwrap

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("ORION_LLM_MODEL", "llama3")
CLAUDE_ENDPOINT = os.getenv("CLAUDE_ENDPOINT", "http://localhost:3000/interpret")

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


def _call_ollama_chat(system_prompt: str, user_text: str) -> str:
    """
    Call Ollama for free-form chat (no JSON).
    """
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


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_pdf_file(path: str) -> str:
    text = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if txt.strip():
                text.append(txt)
    return "\n".join(text)


def extract_text_from_file(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"I couldn't find a file at: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext in [".txt", ".md", ".py", ".json", ".log", ".csv"]:
        return _read_text_file(path)
    elif ext == ".pdf":
        return _read_pdf_file(path)
    else:
        raise ValueError(f"I don't know how to read '{ext}' files yet.")


def summarize_file(path: str, question: str | None = None) -> str:
    """Summarize a file using Ollama."""
    path = os.path.expanduser(path.strip())

    if not path:
        return "You didn't tell me which file to summarize."

    try:
        raw_text = extract_text_from_file(path)
    except Exception as e:
        return f"I couldn't read that file: {e}"

    if not raw_text.strip():
        return "The file seems to be empty or I couldn't extract any text."

    max_chars = 8000
    text_for_model = raw_text[:max_chars]

    if question:
        user_prompt = textwrap.dedent(f"""
        Here is the content of a user file:

        ---
        {text_for_model}
        ---

        1. Give a brief summary of this file (bullet points if helpful).
        2. Then answer this specific question based only on the file:

           "{question}"
        """).strip()
    else:
        user_prompt = textwrap.dedent(f"""
        Here is the content of a user file:

        ---
        {text_for_model}
        ---

        Please provide a clear, concise summary of this file.
        Use bullet points where helpful. Mention the main purpose and key details.
        """).strip()

    system_prompt = """
    You are Orion's document reading assistant.
    You summarize and explain the content of local files.
    Be concise but helpful. If the text looks like code, explain what it does in plain language.
    """.strip()

    try:
        summary = _call_ollama_chat(system_prompt, user_prompt)
        fname = os.path.basename(path)
        return f"Summary of {fname}:\n\n{summary}"
    except Exception as e:
        return f"I couldn't generate a summary right now: {e}"


def get_cloud_command(text: str, memory: dict = None) -> dict:
    """Call Claude API to interpret user command."""
    if memory is None:
        memory = {}
    
    try:
        res = requests.post(
            CLAUDE_ENDPOINT,
            json={"text": text, "memory": memory},
            timeout=10
        )
        res.raise_for_status()
        result = res.json().get("result")
        return result  # should be a dict: {"intent":..., "args":..., "reply":...}
    except Exception as e:
        print(f"[Orion] Cloud AI error: {e}")
        return {"intent": "unknown", "args": {}, "reply": "I couldn't process that."}