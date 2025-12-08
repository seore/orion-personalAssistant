from flask import Flask, render_template_string, request, redirect, url_for
from orion.core import (
    load_data,
    add_note,
    add_task,
    add_reminder,
    complete_task,
)

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Orion Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
            margin: 2rem auto;
            max-width: 900px;
            color: #222;
        }
        h1 {
            margin-bottom: 0.5rem;
        }
        h2 {
            margin-top: 2rem;
            margin-bottom: 0.5rem;
        }
        .section {
            border: 1px solid #ddd;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1.5rem;
            background: #fafafa;
        }
        ul {
            padding-left: 1.2rem;
        }
        li {
            margin-bottom: 0.25rem;
        }
        form {
            margin-top: 0.5rem;
        }
        input[type="text"],
        input[type="datetime-local"],
        textarea {
            width: 100%;
            padding: 0.4rem 0.5rem;
            margin: 0.2rem 0 0.4rem;
            border-radius: 6px;
            border: 1px solid #ccc;
            font: inherit;
            box-sizing: border-box;
        }
        button {
            padding: 0.35rem 0.8rem;
            border-radius: 999px;
            border: none;
            cursor: pointer;
            background: #2563eb;
            color: white;
            font-size: 0.9rem;
        }
        button.secondary {
            background: #e5e7eb;
            color: #111827;
        }
        .task-done {
            text-decoration: line-through;
            color: #6b7280;
        }
        .badge {
            display: inline-block;
            padding: 0.1rem 0.5rem;
            border-radius: 999px;
            font-size: 0.7rem;
            background: #e5e7eb;
            margin-left: 0.3rem;
        }
        .badge.overdue {
            background: #fee2e2;
            color: #b91c1c;
        }
        .badge.pending {
            background: #fef3c7;
            color: #92400e;
        }
        .badge.done {
            background: #dcfce7;
            color: #166534;
        }
        .row {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
        }
        .row > div {
            flex: 1;
        }
        small {
            color: #6b7280;
        }
    </style>
</head>
<body>
    <h1>Orion Dashboard</h1>
    <p><small>View and manage your notes, tasks, and reminders.</small></p>

    <div class="section">
        <h2>Notes</h2>

        {% if notes %}
            <ul>
            {% for n in notes %}
                <li>
                    <strong>#{{ n.id }}</strong> — {{ n.content }}
                    <br><small>{{ n.created_at }}</small>
                </li>
            {% endfor %}
            </ul>
        {% else %}
            <p><em>No notes yet.</em></p>
        {% endif %}

        <form method="post" action="{{ url_for('add_note_route') }}">
            <label for="note_content"><strong>Add note</strong></label><br>
            <textarea id="note_content" name="content" rows="2" placeholder="New note..."></textarea>
            <button type="submit">Save note</button>
        </form>
    </div>

    <div class="section">
        <h2>Tasks</h2>

        {% if tasks %}
            <ul>
            {% for t in tasks %}
                <li>
                    <span class="{{ 'task-done' if t.done else '' }}">
                        <strong>#{{ t.id }}</strong> — {{ t.description }}
                    </span>
                    {% if t.done %}
                        <span class="badge done">done</span>
                    {% else %}
                        <span class="badge pending">pending</span>
                    {% endif %}
                    {% if t.due %}
                        {% if not t.done and t.overdue %}
                            <span class="badge overdue">overdue</span>
                        {% endif %}
                        <br><small>Due: {{ t.due }}</small>
                    {% endif %}

                    {% if not t.done %}
                        <form method="post" action="{{ url_for('complete_task_route', task_id=t.id) }}" style="display:inline;">
                            <button type="submit" class="secondary">Mark done</button>
                        </form>
                    {% endif %}
                </li>
            {% endfor %}
            </ul>
        {% else %}
            <p><em>No tasks yet.</em></p>
        {% endif %}

        <form method="post" action="{{ url_for('add_task_route') }}">
            <label for="task_description"><strong>Add task</strong></label><br>
            <input id="task_description" type="text" name="description" placeholder="Task description...">
            <label for="task_due">Due (optional)</label><br>
            <input id="task_due" type="datetime-local" name="due">
            <button type="submit">Add task</button>
        </form>
    </div>

    <div class="section">
        <h2>Reminders</h2>

        {% if reminders %}
            <ul>
            {% for r in reminders %}
                <li>
                    <strong>#{{ r.id }}</strong> — {{ r.text }}
                    <br>
                    <small>{{ r.time }}</small>
                    {% if r.triggered %}
                        <span class="badge done">triggered</span>
                    {% else %}
                        <span class="badge pending">pending</span>
                    {% endif %}
                </li>
            {% endfor %}
            </ul>
        {% else %}
            <p><em>No reminders yet.</em></p>
        {% endif %}

        <form method="post" action="{{ url_for('add_reminder_route') }}">
            <label for="reminder_text"><strong>Add reminder</strong></label><br>
            <input id="reminder_text" type="text" name="text" placeholder="What should I remind you about?">
            <label for="reminder_time">When</label><br>
            <input id="reminder_time" type="datetime-local" name="time">
            <button type="submit">Set reminder</button>
        </form>
    </div>

</body>
</html>
"""


def _serialize_for_view(data):
    """Turn raw dict from core.load_data() into simple objects for the template."""
    from datetime import datetime

    notes = [
        type("Note", (), n) for n in data.get("notes", [])
    ]

    tasks = []
    now = datetime.now()
    for t in data.get("tasks", []):
        t_obj = type("Task", (), dict(t))  # shallow copy
        if t.get("due"):
            try:
                due_dt = datetime.fromisoformat(t["due"])
                t_obj.overdue = (not t["done"]) and (due_dt < now)
            except ValueError:
                t_obj.overdue = False
        else:
            t_obj.overdue = False
        tasks.append(t_obj)

    reminders = [
        type("Reminder", (), r) for r in data.get("reminders", [])
    ]

    return notes, tasks, reminders


@app.route("/")
def index():
    data = load_data()
    notes, tasks, reminders = _serialize_for_view(data)
    return render_template_string(
        TEMPLATE,
        notes=notes,
        tasks=tasks,
        reminders=reminders,
    )


@app.route("/add_note", methods=["POST"])
def add_note_route():
    content = request.form.get("content", "").strip()
    if content:
        data = load_data()
        add_note(data, content)
    return redirect(url_for("index"))


@app.route("/add_task", methods=["POST"])
def add_task_route():
    description = request.form.get("description", "").strip()
    due_raw = request.form.get("due", "").strip()  # HTML datetime-local format: YYYY-MM-DDTHH:MM
    if description:
        data = load_data()
        due_iso = None
        if due_raw:
            # convert HTML datetime-local "YYYY-MM-DDTHH:MM" -> "YYYY-MM-DD HH:MM"
            due_iso = due_raw.replace("T", " ")
        add_task(data, description, due_iso)
    return redirect(url_for("index"))


@app.route("/add_reminder", methods=["POST"])
def add_reminder_route():
    text = request.form.get("text", "").strip()
    when_raw = request.form.get("time", "").strip()  # HTML datetime-local
    if text and when_raw:
        data = load_data()
        when_iso = when_raw.replace("T", " ")
        add_reminder(data, text, when_iso)
    return redirect(url_for("index"))


@app.route("/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task_route(task_id):
    data = load_data()
    complete_task(data, task_id)
    return redirect(url_for("index"))


if __name__ == "__main__":
    # debug=True auto-reloads when you change this file
    app.run(debug=True)