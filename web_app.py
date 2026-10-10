import re
import time
from pathlib import Path
from flask import Flask, render_template_string, Response, request, jsonify
from board_etl import parse_tasks, shift_line_to_tomorrow, make_line_today, toggle_line_focus
from datetime import datetime

app = Flask(__name__)
TASK_FILE = Path("tasks.txt")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADHD Executive Focus Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background-color: #0f172a; }
        .card { background-color: #1e293b; border-color: #334155; }
        .badge-strong { background-color: #ef4444; }
        .badge-fluid { background-color: #06b6d4; }
        .badge-arbitrary { background-color: #f59e0b; color: #000; }
        .btn-complete { padding: 0.1rem 0.4rem; font-size: 0.75rem; border-radius: 0.25rem; }
    </style>
</head>
<body class="text-light py-4">
    <div class="container">
        <header class="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom border-secondary">
            <h1 class="h3 m-0 text-cyan">⚡ Executive Focus Engine</h1>
            <span class="badge bg-outline-light border text-muted" id="status-badge">Live Sync Active</span>
        </header>

        <div id="dashboard-content">
            {% include 'board_partial.html' %}
        </div>
    </div>

    <script>
        let evtSource;

        function connectSSE() {
            evtSource = new EventSource("/stream");

            evtSource.onmessage = function(e) {
                if (e.data === "reload") {
                    fetch('/partial')
                        .then(res => res.text())
                        .then(html => {
                            document.getElementById('dashboard-content').innerHTML = html;
                            document.getElementById('status-badge').textContent = "Live Sync Active";
                            document.getElementById('status-badge').className = "badge bg-outline-light border text-success";
                        });
                }
            };

            evtSource.onerror = function() {
                // Update status indicator when connection drops
                document.getElementById('status-badge').textContent = "Sync Reconnecting...";
                document.getElementById('status-badge').className = "badge bg-outline-light border text-warning";
                
                evtSource.close();
                // Retry connection after 3 seconds
                setTimeout(connectSSE, 3000);
            };
        }

        connectSSE();

        // Event delegation to capture task completions and shifts
        document.addEventListener('click', function(e) {
            // 1. If any specific action button was clicked, let its handler execute and ignore row-focusing
            if (e.target.closest('button')) {
                const shiftBtn = e.target.closest('.btn-shift-task');
                if (shiftBtn) {
                    const rawLine = shiftBtn.getAttribute('data-raw');
                    fetch('/shift_task', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: rawLine })
                    });
                    return;
                }

                const subtaskBtn = e.target.closest('.btn-complete-subtask');
                if (subtaskBtn) {
                    const parentTitle = subtaskBtn.getAttribute('data-parent');
                    const subtaskText = subtaskBtn.getAttribute('data-subtask');
                    fetch('/complete_subtask', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ parent_title: parentTitle, subtask: subtaskText })
                    });
                    return;
                }

                const taskBtn = e.target.closest('.btn-complete-task');
                if (taskBtn) {
                    const rawLine = taskBtn.getAttribute('data-raw');
                    fetch('/complete_task', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: rawLine })
                    });
                    return;
                }

                const makeTodayBtn = e.target.closest('.btn-make-today');
                if (makeTodayBtn) {
                    const rawLine = makeTodayBtn.getAttribute('data-raw');
                    fetch('/make_today', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: rawLine })
                    });
                    return;
                }

                return; // Exit early if it was another button (e.g. collapse toggle)
            }

            // 2. Otherwise, if any part of the task row was clicked, toggle focus for that task
            const taskRow = e.target.closest('.task-row');
            if (taskRow) {
                const rawLine = taskRow.getAttribute('data-raw');
                fetch('/toggle_focus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ raw_line: rawLine })
                });
            }
        });
</script>
</body>
</html>
"""

PARTIAL_TEMPLATE = """
<!-- Schedule Structure Table (Today) -->
<div class="card mb-4 shadow-sm">
    <div class="card-header fw-bold text-uppercase text-secondary fs-6 d-flex justify-content-between align-items-center">
        <span>Today's Schedule Structure</span>
        <div>
            <span class="badge bg-secondary me-2">{{ data.today|length }} Tasks Total</span>
            {% if data.today|length > 10 %}
            <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#todayCollapse">
                Toggle All {{ data.today|length }} Tasks
            </button>
            {% endif %}
        </div>
    </div>
    <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-dark table-hover m-0 align-middle">
                <thead>
                    <tr class="text-secondary">
                        <th style="width: 12%">Type</th>
                        <th style="width: 18%">Time / Date</th>
                        <th style="width: 12%">Context</th>
                        <th>Task Description</th>
                        <th>Tags</th>
                        <th style="width: 12%" class="text-end">Action</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- First 10 Tasks (Always Visible) -->
                    {% for t in data.today[:10] %}
                        <!-- Table Row for t in data.today -->
                        <tr class="task-row {% if 'focus' in t.tags %}table-primary text-light fw-bold border-start border-4 border-info{% endif %}"
                            data-raw="{{ t.raw|forceescape }}"
                            style="cursor: pointer;">
                            <td class="align-top">
                                {% if 'focus' in t.tags %}
                                    <span class="badge bg-info text-dark">🎯 IN FOCUS</span>
                                {% elif t.symbol == '!' %}
                                    <span class="badge badge-strong">STRONG</span>
                                {% elif t.symbol == '?' %}
                                    <span class="badge badge-arbitrary">ARBITRARY</span>
                                {% else %}
                                    <span class="badge badge-fluid">FLUID</span>
                                {% endif %}
                            </td>
                            <td class="text-info fw-semibold align-top">{{ t.time or 'Flexible' }}</td>
                            <td class="align-top">
                                {% if t.contexts %}
                                    <span class="badge bg-secondary">@{{ t.contexts[0] }}</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="{% if t.symbol == '?' %}text-muted fst-italic{% else %}fw-semibold{% endif %}">
                                    {{ t.title }}
                                </div>
                                {% if t.subtasks %}
                                    <ul class="list-unstyled ms-3 mt-2 mb-0 small">
                                        {% for sub in t.subtasks %}
                                            <li class="d-flex align-items-center justify-content-between mb-1">
                                                <span>
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-secondary{% endif %}">↳</span> 
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-muted{% endif %}">{{ sub }}</span>
                                                </span>
                                                <button 
                                                    data-parent="{{ t.title|forceescape }}" 
                                                    data-subtask="{{ sub|forceescape }}" 
                                                    class="btn {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete btn-complete-subtask ms-2">✓ Done</button>
                                            </li>
                                        {% endfor %}
                                    </ul>
                                {% endif %}
                            </td>
                            <td class="align-top">
                                {% for tag in t.tags %}
                                    {% if tag != 'focus' %}
                                        <span class="badge bg-dark border border-secondary text-light">#{{ tag }}</span>
                                    {% endif %}
                                {% endfor %}
                            </td>
                            <td class="align-top text-end">
                                <div class="btn-group btn-group-sm">
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-warning border-warning{% else %}btn-outline-warning{% endif %} btn-shift-task">➡️ Tomorrow</button>
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete-task">✓ Done</button>
                                </div>
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>

            <!-- Overflow Tasks (Collapsed if > 10) -->
            {% if data.today|length > 10 %}
            <div class="collapse" id="todayCollapse">
                <table class="table table-dark table-hover m-0 align-middle border-top border-secondary">
                    <tbody>
                        {% for t in data.today[10:] %}
                        <tr class="task-row {% if 'focus' in t.tags %}table-primary text-light fw-bold border-start border-4 border-info{% endif %}"
                            data-raw="{{ t.raw|forceescape }}"
                            style="cursor: pointer;">
                            <td style="width: 12%" class="align-top">
                                {% if 'focus' in t.tags %}
                                    <span class="badge bg-info text-dark">🎯 IN FOCUS</span>
                                {% elif t.symbol == '!' %}
                                    <span class="badge badge-strong">STRONG</span>
                                {% elif t.symbol == '?' %}
                                    <span class="badge badge-arbitrary">ARBITRARY</span>
                                {% else %}
                                    <span class="badge badge-fluid">FLUID</span>
                                {% endif %}
                            </td>
                            <td style="width: 18%" class="text-info fw-semibold align-top">{{ t.time or 'Flexible' }}</td>
                            <td style="width: 12%" class="align-top">
                                {% if t.contexts %}
                                    <span class="badge bg-secondary">@{{ t.contexts[0] }}</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="{% if t.symbol == '?' %}text-muted fst-italic{% else %}fw-semibold{% endif %}">
                                    {{ t.title }}
                                </div>
                                {% if t.subtasks %}
                                    <ul class="list-unstyled ms-3 mt-2 mb-0 small">
                                        {% for sub in t.subtasks %}
                                            <li class="d-flex align-items-center justify-content-between mb-1">
                                                <span>
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-secondary{% endif %}">↳</span> 
                                                    <span class="{% if 'focus' in t.tags %}text-dark{% else %}text-muted{% endif %}">{{ sub }}</span>
                                                </span>
                                                <button 
                                                    data-parent="{{ t.title|forceescape }}" 
                                                    data-subtask="{{ sub|forceescape }}" 
                                                    class="btn {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete btn-complete-subtask ms-2">✓ Done</button>
                                            </li>
                                        {% endfor %}
                                    </ul>
                                {% endif %}
                            </td>
                            <td class="align-top">
                                {% for tag in t.tags %}
                                    {% if tag != 'focus' %}
                                        <span class="badge bg-dark border border-secondary text-light">#{{ tag }}</span>
                                    {% endif %}
                                {% endfor %}
                            </td>
                            <td style="width: 12%" class="align-top text-end">
                                <div class="btn-group btn-group-sm">
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-warning border-warning{% else %}btn-outline-warning{% endif %} btn-shift-task">➡️ Tomorrow</button>
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete-task">✓ Done</button>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}

            {% if not data.today %}
            <table class="table table-dark m-0">
                <tbody>
                    <tr>
                        <td colspan="6" class="text-center text-muted py-3 fst-italic">No active tasks scheduled for today!</td>
                    </tr>
                </tbody>
            </table>
            {% endif %}
        </div>
    </div>
</div>

<!-- Future Scheduled Tasks -->
{% if data.future %}
<div class="card mb-4 border-info shadow-sm">
    <div class="card-header bg-dark text-info fw-bold d-flex justify-content-between align-items-center">
        <span>📅 Future Scheduled Tasks ({{ data.future|length }} Total)</span>
        <button class="btn btn-sm btn-outline-info" type="button" data-bs-toggle="collapse" data-bs-target="#futureCollapse">
            Toggle All {{ data.future|length }} Items
        </button>
    </div>
    <div class="card-body p-0">
        <!-- Initial 3 Preview Items -->
        <ul class="list-group list-group-flush border-bottom border-secondary">
            {% for t in data.future[:3] %}
                <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between align-items-center">
                    <div>
                        <span class="badge bg-info text-dark me-2">{{ t.time }}</span>
                        <span class="fw-semibold">{{ t.title }}</span>
                        {% if t.contexts %}<span class="badge bg-secondary ms-2">@{{ t.contexts[0] }}</span>{% endif %}
                    </div>
                    <button 
                        data-raw="{{ t.raw|forceescape }}" 
                        class="btn btn-sm btn-outline-info btn-make-today">📌 Today</button>
                </li>
            {% endfor %}
        </ul>
        
        <!-- Expanded Remaining Items -->
        {% if data.future|length > 3 %}
        <div class="collapse" id="futureCollapse">
            <ul class="list-group list-group-flush">
                {% for t in data.future[3:] %}
                    <li class="list-group-item bg-transparent text-muted border-secondary d-flex justify-content-between align-items-center">
                        <div>
                            <span class="badge bg-secondary me-2">{{ t.time }}</span>
                            <span>{{ t.title }}</span>
                            {% if t.contexts %}<span class="badge bg-secondary ms-2">@{{ t.contexts[0] }}</span>{% endif %}
                        </div>
                        <button 
                            data-raw="{{ t.raw|forceescape }}" 
                            class="btn btn-sm btn-outline-info btn-make-today">📌 Today</button>
                    </li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}
    </div>
</div>
{% endif %}

<div class="row g-4 mb-4">
    <!-- Low-Hanging Fruit -->
    <div class="col-md-6">
        <div class="card h-100 border-success shadow-sm">
            <div class="card-header bg-success text-white fw-bold">
                ⚡ Low-Hanging Fruit (<15m / Low Energy)
            </div>
            <ul class="list-group list-group-flush">
                {% set quick_count = namespace(value=0) %}
                {% for t in data.today %}
                    {% if 'quick' in t.tags or 'low_energy' in t.tags %}
                        {% set quick_count.value = quick_count.value + 1 %}
                        <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between align-items-center">
                            <span>{{ t.title }}</span>
                            <button data-raw="{{ t.raw|forceescape }}" class="btn btn-outline-success btn-complete btn-complete-task">✓</button>
                        </li>
                    {% endif %}
                {% endfor %}
                {% if quick_count.value == 0 %}
                    <li class="list-group-item bg-transparent text-muted fst-italic border-secondary">None logged</li>
                {% endif %}
            </ul>
        </div>
    </div>

    <!-- Gap Fillers -->
    <div class="col-md-6">
        <div class="card h-100 border-warning shadow-sm">
            <div class="card-header bg-warning text-dark fw-bold">
                ⏳ Gap Fillers (While Waiting on Main Task)
            </div>
            <ul class="list-group list-group-flush">
                {% set wait_count = namespace(value=0) %}
                {% for t in data.today %}
                    {% set has_wait = false %}
                    {% for tag in t.tags %}
                        {% if tag == 'wait' or tag.startswith('wait:') %}
                            {% set has_wait = true %}
                        {% endif %}
                    {% endfor %}
                    
                    {% if has_wait %}
                        {% set wait_count.value = wait_count.value + 1 %}
                        <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between align-items-center">
                            <span>{{ t.title }}</span>
                            <div>
                                {% for tag in t.tags %}
                                    {% if tag == 'wait' or tag.startswith('wait:') %}
                                        <span class="badge bg-secondary me-2">#{{ tag }}</span>
                                    {% endif %}
                                {% endfor %}
                                <button data-raw="{{ t.raw|forceescape }}" class="btn btn-outline-success btn-complete btn-complete-task">✓</button>
                            </div>
                        </li>
                    {% endif %}
                {% endfor %}
                {% if wait_count.value == 0 %}
                    <li class="list-group-item bg-transparent text-muted fst-italic border-secondary">None logged</li>
                {% endif %}
            </ul>
        </div>
    </div>
</div>

<!-- Collapsible Completed Items Panel -->
{% if data.completed %}
<div class="card border-secondary">
    <div class="card-header bg-dark text-muted d-flex justify-content-between align-items-center">
        <span>Completed Tasks</span>
        <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#completedCollapse">
            View {{ data.completed|length }} Completed Items
        </button>
    </div>
    <div class="collapse" id="completedCollapse">
        <ul class="list-group list-group-flush">
            {% for item in data.completed %}
                <li class="list-group-item bg-transparent text-muted text-decoration-line-through border-secondary small">
                    ✓ {{ item }}
                </li>
            {% endfor %}
        </ul>
    </div>
</div>
{% endif %}
"""

# Helpers

def insert_date_at_front(raw_line: str, date_str: str) -> str:
    """
    Inserts date_str right after the task symbol (!, *, ?), or at the beginning 
    if no symbol is present.
    Example: "* Dry Whites" -> "* 10/9 Dry Whites"
    """
    stripped = raw_line.strip()
    if stripped and stripped[0] in "!*?":
        symbol = stripped[0]
        content = stripped[1:].strip()
        return f"{symbol} {date_str} {content}"
    return f"{date_str} {stripped}"

# Endpoints

@app.route("/")
def index():
    data = parse_tasks(str(TASK_FILE))
    return render_template_string(
        HTML_TEMPLATE.replace("{% include 'board_partial.html' %}", PARTIAL_TEMPLATE), 
        data=data
    )

@app.route("/partial")
def partial():
    data = parse_tasks(str(TASK_FILE))
    return render_template_string(PARTIAL_TEMPLATE, data=data)

@app.route("/shift_task", methods=["POST"])
def shift_task():
    req_data = request.get_json()
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []

    for line in lines:
        if line.strip() == raw_line.strip():
            # Shift task date to tomorrow
            new_lines.append(shift_line_to_tomorrow(line))
        else:
            new_lines.append(line)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

@app.route("/stream")
def stream():
    def event_stream():
        last_mtime = 0
        while True:
            if TASK_FILE.exists():
                mtime = TASK_FILE.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    yield "data: reload\n\n"
            
            # Send periodic keep-alive comment every 15s to keep connection open
            yield ": keep-alive\n\n"
            time.sleep(0.5)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/toggle_focus", methods=["POST"])
def toggle_focus():
    req_data = request.get_json()
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    toggle_line_focus(str(TASK_FILE), raw_line)
    return jsonify({"status": "ok"})

@app.route("/complete_subtask", methods=["POST"])
def complete_subtask():
    req_data = request.get_json()
    parent_title = req_data.get("parent_title")
    subtask_text = req_data.get("subtask")

    if not parent_title or not subtask_text or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []
    parent_line_idx = None
    remaining_subtasks_count = 0
    in_target_parent = False

    for idx, line in enumerate(lines):
        stripped = line.strip()

        if stripped and stripped[0] in "!*?" and parent_title in line:
            in_target_parent = True
            parent_line_idx = idx
            new_lines.append(line)
            continue

        if in_target_parent and (line.startswith(" ") or line.startswith("\t")):
            if subtask_text in line:
                continue
            else:
                remaining_subtasks_count += 1
        elif stripped and stripped[0] in "!*?#":
            in_target_parent = False

        new_lines.append(line)

    # If no remaining subtasks, auto-complete parent task
    if parent_line_idx is not None and remaining_subtasks_count == 0:
        parent_raw = lines[parent_line_idx].strip()
        final_lines = [l for l in new_lines if l.strip() != parent_raw]
        
        date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', parent_raw)
        now = datetime.now()
        today_str = f"{now.month}/{now.day}"
        
        if not date_match:
            parent_raw = insert_date_at_front(parent_raw, today_str)

        if "# Done" not in final_lines:
            final_lines.append("\n# Done")
        final_lines.append(f"x {parent_raw}")
        TASK_FILE.write_text("\n".join(final_lines) + "\n")
    else:
        TASK_FILE.write_text("\n".join(new_lines) + "\n")

    return jsonify({"status": "ok"})

@app.route("/complete_task", methods=["POST"])
def complete_task():
    req_data = request.get_json()
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []
    completed_block = []
    removing = False

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    for line in lines:
        if line.strip() == raw_line.strip():
            removing = True
            
            # Check if line already has an explicit M/D date
            date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', line)
            if not date_match:
                # Insert today's date at the front after symbol
                completed_block.append(insert_date_at_front(line, today_str))
            else:
                completed_block.append(line.strip())
            continue
        
        if removing and (line.startswith(" ") or line.startswith("\t")):
            completed_block.append(line.strip())
            continue
        else:
            removing = False

        new_lines.append(line)

    if completed_block:
        if "# Done" not in new_lines:
            new_lines.append("\n# Done")
        for item in completed_block:
            clean_item = re.sub(r'^(?:x\s*)+', '', item)
            new_lines.append(f"x {clean_item}")
        TASK_FILE.write_text("\n".join(new_lines) + "\n")

    return jsonify({"status": "ok"})

@app.route("/make_today", methods=["POST"])
def make_today():
    req_data = request.get_json()
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []

    for line in lines:
        if line.strip() == raw_line.strip():
            new_lines.append(make_line_today(line))
        else:
            new_lines.append(line)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    if not TASK_FILE.exists():
        TASK_FILE.write_text("! 10:30 - 11:00 Weekly Sync @admin #30-min\n* Dry Whites @home #wait\n")
    
    print("Serving Bootstrap 5 Dashboard at http://127.0.0.1:5000")
    app.run(port=5000, debug=True)