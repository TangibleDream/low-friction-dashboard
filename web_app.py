import re
import time
from pathlib import Path
from flask import Flask, render_template_string, Response, request, jsonify
from utils.board_etl import parse_tasks, shift_line_to_tomorrow, make_line_today, toggle_line_focus, move_line_to_bottom, delete_line
from datetime import datetime
from utils.ics_utils import generate_task_ics

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
        
        function initTooltips() {
            const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            [...tooltipTriggerList].map(tooltipTriggerEl => bootstrap.Tooltip.getOrCreateInstance(tooltipTriggerEl));
        }

        document.addEventListener("DOMContentLoaded", initTooltips);

        function connectSSE() {
            evtSource = new EventSource("/stream");

            evtSource.onmessage = function(e) {
                if (e.data === "reload") {
                    fetch('/partial')
                        .then(res => res.text())
                        .then(html => {
                            document.getElementById('dashboard-content').innerHTML = html;
                            initTooltips();
                        });
                }
            };

            evtSource.onerror = function() {
                document.getElementById('status-badge').textContent = "Sync Reconnecting...";
                document.getElementById('status-badge').className = "badge bg-outline-light border text-warning";
                
                evtSource.close();
                setTimeout(connectSSE, 3000);
            };
        }

        connectSSE();

        document.addEventListener('click', function(e) {
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

                const deleteBtn = e.target.closest('.btn-delete-task');
                if (deleteBtn) {
                    const tooltip = bootstrap.Tooltip.getInstance(deleteBtn);
                    if (tooltip) tooltip.hide();

                    fetch('/delete_task', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: deleteBtn.getAttribute('data-raw') })
                    });
                    return;
                }

                const moveBottomBtn = e.target.closest('.btn-move-bottom');
                if (moveBottomBtn) {
                    const tooltip = bootstrap.Tooltip.getInstance(moveBottomBtn);
                    if (tooltip) tooltip.hide();

                    fetch('/move_to_bottom', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ raw_line: moveBottomBtn.getAttribute('data-raw') })
                    });
                    return;
                }

                return;
            }

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

        document.addEventListener('click', function(e) {
            if (e.target && e.target.id === 'btn-add-subtask-field') {
                const container = document.getElementById('subtasks-container');
                const row = document.createElement('div');
                row.className = 'input-group input-group-sm mb-1 subtask-row';
                row.innerHTML = `
                    <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                    <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                    <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                `;
                container.appendChild(row);
                row.querySelector('input').focus();
                return;
            }

            const removeBtn = e.target.closest('.btn-remove-subtask');
            if (removeBtn) {
                const row = removeBtn.closest('.subtask-row');
                if (row) row.remove();
                return;
            }
        });

        document.addEventListener('click', function(e) {
            if (e.target && e.target.id === 'btn-save-task') {
                const dateVal = document.getElementById('task-date').value;
                const symbol = document.getElementById('task-type').value;
                const description = document.getElementById('task-desc').value.trim();
                const rawTags = document.getElementById('task-tags-input').value.trim();

                if (!description) {
                    document.getElementById('task-desc').classList.add('is-invalid');
                    return;
                }

                const tags = rawTags ? rawTags.split(/\s+/).map(t => t.replace(/^#/, '')) : [];
                const subtaskInputs = document.querySelectorAll('.subtask-input');
                const subtasks = Array.from(subtaskInputs)
                    .map(input => input.value.trim())
                    .filter(val => val.length > 0);

                fetch('/add_task', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ date: dateVal, symbol, description, tags, subtasks })
                }).then(res => {
                    if (res.ok) {
                        const modalEl = document.getElementById('addTaskModal');
                        const modal = bootstrap.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                        document.getElementById('create-task-form').reset();
                        
                        document.getElementById('subtasks-container').innerHTML = `
                            <div class="input-group input-group-sm mb-1 subtask-row">
                                <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                                <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                                <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                            </div>
                        `;
                    }
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
        <div class="d-flex align-items-center gap-2">
            <span class="badge bg-secondary">{{ data.today|length }} Tasks Total</span>
            {% if data.today|length > 10 %}
            <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#todayCollapse">
                Toggle All
            </button>
            {% endif %}
            <button class="btn btn-sm btn-info text-dark fw-bold px-2" type="button" data-bs-toggle="modal" data-bs-target="#addTaskModal">
                ＋ Task
            </button>
        </div>
    </div>

    <!-- Task Creation Modal -->
    <div class="modal fade" id="addTaskModal" tabindex="-1" aria-labelledby="addTaskModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-light border border-secondary shadow-lg">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title fs-6 fw-bold text-info" id="addTaskModalLabel">📌 Create Scheduled Task</h5>
                </div>
                <div class="modal-body">
                    <form id="create-task-form">
                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">SCHEDULED DATE</label>
                            <input type="date" class="form-control bg-dark text-light border-secondary" id="task-date" value="{{ data.today_iso }}">
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">TASK TYPE</label>
                            <select class="form-select bg-dark text-light border-secondary" id="task-type">
                                <option value="*" selected>* Fluid Task (Default)</option>
                                <option value="!">! Strong Commitment</option>
                                <option value="?">? Arbitrary / Optional</option>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">TASK DESCRIPTION</label>
                            <input type="text" class="form-control bg-dark text-light border-secondary" id="task-desc" placeholder="e.g. Review pull request" required autocomplete="off">
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold">TAGS (Type or select historical)</label>
                            <input type="text" class="form-control bg-dark text-light border-secondary" id="task-tags-input" list="historical-tags-list" placeholder="e.g. priority work">
                            <datalist id="historical-tags-list">
                                {% for tag in data.all_tags %}
                                    <option value="{{ tag }}"></option>
                                {% endfor %}
                            </datalist>
                            <div class="form-text text-muted small">Space-separated tags. Selecting <code>priority</code> moves item to the top.</div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label text-secondary small fw-bold d-flex justify-content-between align-items-center">
                                <span>SUBTASKS (Optional)</span>
                                <button type="button" class="btn btn-sm btn-outline-info py-0 px-2 fs-7" id="btn-add-subtask-field">＋ Add Subtask</button>
                            </label>
                            <div id="subtasks-container">
                                <div class="input-group input-group-sm mb-1 subtask-row">
                                    <span class="input-group-text bg-dark border-secondary text-secondary">↳</span>
                                    <input type="text" class="form-control bg-dark text-light border-secondary subtask-input" placeholder="Subtask description">
                                    <button type="button" class="btn btn-outline-danger btn-remove-subtask">✕</button>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-sm btn-info text-dark fw-bold" id="btn-save-task">Save Task</button>
                </div>
            </div>
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
                    {% for t in data.today[:10] %}
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
                                {% if 'focus' in t.tags %}
                                <div class="btn-group btn-group-sm">
                                    {% if t.time %}
                                    <button 
                                        <!-- Inside PARTIAL_TEMPLATE action group -->
                                        <a 
                                            href="/export_ics?title={{ t.title|urlencode }}&date={{ t.parsed_date.strftime('%Y-%m-%d') if t.parsed_date else data.today_iso }}&time={{ t.time|urlencode if t.time else '' }}" 
                                            class="btn btn-dark text-info border-info"
                                            data-bs-toggle="tooltip"
                                            data-bs-placement="top"
                                            title="Export to Outlook/iCal">📅 Add to Calendar</a>
                                    {% endif %}

                                    {% if 'priority' not in t.tags %}
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-secondary border-secondary btn-move-bottom"
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Move task to bottom">⬇️</button>
                                    {% endif %}

                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-warning border-warning btn-shift-task">➡️ Tomorrow</button>

                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-success border-success btn-complete-task">✓ Done</button>

                                    <button 
                                        type="button" 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-danger border-danger btn-delete-task" 
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Delete task">✕</button>
                                </div>
                                {% endif %}
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>

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
                                {% if 'focus' in t.tags %}
                                <div class="btn-group btn-group-sm">
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-warning border-warning{% else %}btn-outline-warning{% endif %} btn-shift-task">➡️ Tomorrow</button>
                                    <button 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn {% if 'focus' in t.tags %}btn-dark text-success border-success{% else %}btn-outline-success{% endif %} btn-complete-task">✓ Done</button>
                                    <button 
                                        type="button" 
                                        data-raw="{{ t.raw|forceescape }}" 
                                        class="btn btn-dark text-danger border-danger btn-delete-task" 
                                        data-bs-toggle="tooltip"
                                        data-bs-placement="top"
                                        title="Delete task">✕</button>
                                </div>
                                {% endif %}
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

@app.route("/add_task", methods=["POST"])
def add_task():
    req_data = request.get_json()
    symbol = req_data.get("symbol", "*")
    description = req_data.get("description", "").strip()
    tags = req_data.get("tags", [])
    subtasks = req_data.get("subtasks", [])
    selected_date_str = req_data.get("date")

    if not description or not TASK_FILE.exists():
        return jsonify({"status": "error", "message": "Description required"}), 400

    if selected_date_str:
        try:
            target_dt = datetime.strptime(selected_date_str, "%Y-%m-%d")
        except ValueError:
            target_dt = datetime.now()
    else:
        target_dt = datetime.now()

    date_shorthand = f"{target_dt.month}/{target_dt.day}"

    formatted_tags = " ".join([f"#{t.strip('#')}" for t in tags if t.strip()])
    parent_line = f"{symbol} {date_shorthand} {description}"
    if formatted_tags:
        parent_line += f" {formatted_tags}"

    task_block = [parent_line]
    for sub in subtasks:
        sub_clean = sub.strip()
        if sub_clean:
            task_block.append(f"  * {sub_clean}")

    lines = TASK_FILE.read_text().splitlines()
    new_lines = []
    inserted = False

    for line in lines:
        if line.strip() == "# Done" and not inserted:
            new_lines.extend(task_block)
            new_lines.append("")
            inserted = True
        new_lines.append(line)

    if not inserted:
        new_lines.extend(task_block)

    TASK_FILE.write_text("\n".join(new_lines) + "\n")
    return jsonify({"status": "ok"})

@app.route("/delete_task", methods=["POST"])
def delete_task():
    req_data = request.get_json() or {}
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    delete_line(str(TASK_FILE), raw_line)
    return jsonify({"status": "ok"})

@app.route("/export_ics", methods=["GET"])
def export_ics():
    title = request.args.get("title", "Scheduled Task")
    date_str = request.args.get("date")
    time_str = request.args.get("time")

    ics_data = generate_task_ics(title=title, date_str=date_str, time_str=time_str)
    
    safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', title).lower()[:20] or "task"
    
    return Response(
        ics_data,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={safe_filename}.ics"}
    )

@app.route("/move_to_bottom", methods=["POST"])
def move_to_bottom():
    req_data = request.get_json() or {}
    raw_line = req_data.get("raw_line")

    if not raw_line or not TASK_FILE.exists():
        return jsonify({"status": "error"}), 400

    move_line_to_bottom(str(TASK_FILE), raw_line)
    return jsonify({"status": "ok"})

@app.route("/partial")
def partial():
    data = parse_tasks(str(TASK_FILE))
    data["today_iso"] = datetime.now().strftime("%Y-%m-%d")
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
            
            date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', line)
            if not date_match:
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